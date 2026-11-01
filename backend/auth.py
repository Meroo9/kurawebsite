import secrets, hashlib, asyncio
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pymongo.errors import DuplicateKeyError
from pymongo import ReturnDocument
import bcrypt
from core import db, uid, stamp, now, digest, current_user, optional_user, limit, audit, normalized_phone, Document, ORIGIN
from schemas import Register, Login, Profile, Forgot, Reset, Claim
from mailer import send_reset_email

router = APIRouter(prefix='/auth', tags=['accounts'])

def hash_password(password):
    return bcrypt.hashpw(hashlib.sha256(password.encode()).digest(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    return bcrypt.checkpw(hashlib.sha256(password.encode()).digest(), hashed.encode())

async def session_for(user, response):
    token = secrets.token_urlsafe(40)
    await db.sessions.insert_one({'token_hash': digest(token), 'user_id': user['id'], 'expires_at': now() + timedelta(days=7)})
    response.set_cookie('kura_session', token, max_age=604800, httponly=True, secure=True, samesite='lax', path='/api')

def profile_data(data):
    result = data.model_dump(mode='json', exclude={'email','password'})
    result['name'] = result['name'].strip()
    if len(result['name']) < 2: raise HTTPException(422, 'أدخل الاسم الكامل بصورة صحيحة')
    result['phone'] = normalized_phone(result['phone'])
    if result['is_student'] and (not result['university'].strip() or not result['research_field'].strip()):
        raise HTTPException(422, 'أكمل الجامعة والمجال البحثي')
    if result['krc'] and (not result['registration_date'] or not result['university'].strip() or not result['research_field'].strip()):
        raise HTTPException(422, 'أكمل بيانات التسجيل في كورا والجامعة والمجال البحثي')
    if result['registration_date'] and result['registration_date'] > now().date().isoformat():
        raise HTTPException(422, 'تاريخ التسجيل لا يمكن أن يكون في المستقبل')
    return result

@router.post('/register', response_model=Document)
async def register(data: Register, request: Request, response: Response):
    await limit(request, 'register', 12)
    user = {**profile_data(data), 'id': uid(), 'email': str(data.email).lower(), 'role': 'visitor', 'status': 'active', 'student_status': 'pending' if data.krc else 'none', 'avatar_id': None, 'created_at': stamp()}
    stored = {**user, 'password_hash': await asyncio.to_thread(hash_password, data.password)}
    try: await db.users.insert_one(stored)
    except DuplicateKeyError: raise HTTPException(409, 'البريد الإلكتروني أو الهاتف أو رقم كورا مستخدم بالفعل')
    await session_for(user, response)
    await audit(user['id'], 'account_created', user['id'])
    return user

@router.post('/login', response_model=Document)
async def login(data: Login, request: Request, response: Response):
    await limit(request, 'login', 30)
    user = await db.users.find_one({'email': str(data.email).lower()}, {'_id': 0})
    if not user or not await asyncio.to_thread(check_password, data.password, user['password_hash']):
        raise HTTPException(401, 'البريد الإلكتروني أو كلمة المرور غير صحيحة')
    if user['status'] != 'active': raise HTTPException(403, 'هذا الحساب موقوف. يرجى التواصل مع الإدارة')
    user.pop('password_hash')
    await session_for(user, response)
    return user

@router.get('/me', response_model=Document)
async def me(user=Depends(current_user)): return user

@router.post('/logout')
async def logout(request: Request, response: Response):
    await db.sessions.delete_many({'token_hash': digest(request.cookies.get('kura_session', ''))})
    response.delete_cookie('kura_session', path='/api', secure=True, httponly=True, samesite='lax')
    return {'success': True}

@router.put('/profile', response_model=Document)
async def edit_profile(data: Profile, user=Depends(current_user)):
    update = profile_data(data)
    if user['role'] == 'student' and update['krc'] != user.get('krc'):
        raise HTTPException(403, 'رقم كورا المعتمد لا يمكن تغييره إلا بواسطة الإدارة')
    if update['krc'] != user.get('krc') or (update['krc'] and user.get('student_status') == 'rejected'):
        update['student_status'] = 'pending' if update['krc'] else 'none'
    try: await db.users.update_one({'id': user['id']}, {'$set': update})
    except DuplicateKeyError: raise HTTPException(409, 'الهاتف أو رقم كورا مستخدم بالفعل')
    return await db.users.find_one({'id': user['id']}, {'_id': 0, 'password_hash': 0})

@router.post('/forgot-password')
async def forgot(data: Forgot, request: Request):
    await limit(request, 'forgot', 5)
    user = await db.users.find_one({'email': str(data.email).lower(), 'status': 'active'}, {'_id': 0})
    if user:
        token = secrets.token_urlsafe(40)
        await db.reset_tokens.delete_many({'user_id': user['id']})
        await db.reset_tokens.insert_one({'token_hash': digest(token), 'user_id': user['id'], 'expires_at': now() + timedelta(minutes=30)})
        try: await send_reset_email(user, f'{ORIGIN}/reset-password#token={token}')
        except HTTPException:
            import logging
            logging.getLogger(__name__).warning('Password reset delivery unavailable')
            await db.reset_tokens.delete_one({'token_hash': digest(token)})
    return {'message': 'إذا كان البريد مرتبطًا بحساب نشط، فستصلك رسالة استعادة كلمة المرور. تحقق من البريد غير المرغوب فيه أيضًا.'}

@router.post('/reset-password')
async def reset(data: Reset, request: Request):
    await limit(request, 'reset', 15)
    record = await db.reset_tokens.find_one_and_delete({'token_hash': digest(data.token), 'expires_at': {'$gt': now()}}, projection={'_id': 0})
    if not record: raise HTTPException(400, 'الرابط منتهي الصلاحية أو مستخدم. اطلب رابطًا جديدًا')
    await db.users.update_one({'id': record['user_id']}, {'$set': {'password_hash': await asyncio.to_thread(hash_password, data.password)}})
    await db.sessions.delete_many({'user_id': record['user_id']})
    await audit(record['user_id'], 'password_reset')
    return {'message': 'تم تغيير كلمة المرور. يمكنك تسجيل الدخول الآن'}

@router.post('/activate-owner')
async def activate(data: Claim, request: Request, user=Depends(current_user)):
    await limit(request, 'owner', 5)
    invite = await db.owner_invites.find_one_and_update({'token_hash': digest(data.token), 'used': False, 'expires_at': {'$gt': now()}}, {'$set': {'used': True, 'user_id': user['id']}}, projection={'_id': 0}, return_document=ReturnDocument.AFTER)
    if not invite: raise HTTPException(400, 'رابط التفعيل غير صالح أو مستخدم')
    await db.users.update_one({'id': user['id']}, {'$set': {'role': 'admin'}})
    await audit(user['id'], 'owner_activated')
    return {'message': 'تم تفعيل حساب مدير المنصة'}