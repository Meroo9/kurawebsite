import os, secrets, hashlib, re
from pathlib import Path
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from fastapi import Request, HTTPException, Depends
from pydantic import BaseModel, ConfigDict

load_dotenv(Path(__file__).parent / '.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]
ORIGIN = os.environ['APP_ORIGIN'].rstrip('/')

class Document(BaseModel):
    model_config = ConfigDict(extra='allow')

def uid(): return secrets.token_hex(12)
def now(): return datetime.now(timezone.utc)
def stamp(): return now().isoformat()
def digest(value): return hashlib.sha256(value.encode()).hexdigest()

async def audit(user_id, action, target='', details=''):
    await db.audit.insert_one({'id': uid(), 'user_id': user_id, 'action': action, 'target': target, 'details': details, 'created_at': stamp()})

async def limit(request, action, maximum=15):
    key = f'{action}:{request.client.host}:{int(now().timestamp()) // 900}'
    from pymongo import ReturnDocument
    row = await db.rate_limits.find_one_and_update({'_id': key}, {'$inc': {'count': 1}, '$setOnInsert': {'expires_at': now() + timedelta(minutes=20)}}, upsert=True, return_document=ReturnDocument.AFTER)
    if row['count'] > maximum: raise HTTPException(429, 'محاولات كثيرة. يرجى المحاولة بعد قليل')

async def optional_user(request: Request):
    token = request.cookies.get('kura_session')
    if not token: return None
    session = await db.sessions.find_one({'token_hash': digest(token), 'expires_at': {'$gt': now()}}, {'_id': 0})
    if not session: return None
    return await db.users.find_one({'id': session['user_id']}, {'_id': 0, 'password_hash': 0})

async def current_user(user=Depends(optional_user)):
    if not user: raise HTTPException(401, 'يرجى تسجيل الدخول')
    if user['status'] != 'active': raise HTTPException(403, 'هذا الحساب موقوف. يرجى التواصل مع الإدارة')
    return user

async def admin_user(user=Depends(current_user)):
    if user['role'] != 'admin': raise HTTPException(403, 'هذه الصفحة مخصصة للإدارة')
    return user

def normalized_phone(value):
    value = ''.join(str(int(c)) if c.isdecimal() else c for c in value.strip())
    value = re.sub(r'[\s()\-]', '', value)
    if value.startswith('00'): value = '+' + value[2:]
    if not re.fullmatch(r'\+?[0-9]{7,15}', value): raise HTTPException(422, 'يرجى إدخال رقم هاتف صحيح')
    return value

async def course_access(user, course):
    if not user or user['status'] != 'active' or course.get('deleted'): return False
    if user['role'] == 'admin': return True
    purchased = await db.purchases.count_documents({'user_id': user['id'], 'course_id': course['id'], 'status': 'approved'})
    return bool(purchased or (course['published'] and (course['price_minor'] == 0 or (user['role'] == 'student' and course['free_for_students']))))