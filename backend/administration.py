import re, asyncio
from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.errors import DuplicateKeyError
from pydantic import EmailStr, TypeAdapter
from core import db, uid, stamp, admin_user, normalized_phone, audit, Document
from auth import profile_data, hash_password
from schemas import UserEdit, Register, SettingsInput

router=APIRouter(prefix='/admin',tags=['administration'])

@router.get('/operations-summary',response_model=Document)
async def operations_summary(user=Depends(admin_user)):
    return {'waiting_quote':await db.research_requests.count_documents({'status':'waiting_quote'}),'research_receipts':await db.research_requests.count_documents({'payment_status':'pending','status':{'$ne':'cancelled'}}),'published_posts':await db.posts.count_documents({'published':True,'deleted':False})}

@router.get('/overview',response_model=Document)
async def overview(user=Depends(admin_user)):
    return {'users':await db.users.count_documents({}), 'courses':await db.courses.count_documents({'deleted':{'$ne':True}}), 'pending_receipts':await db.purchases.count_documents({'status':'pending'}), 'pending_students':await db.users.count_documents({'student_status':'pending'}), 'recent':await db.audit.find({}, {'_id':0}).sort('created_at',-1).limit(8).to_list(8)}

@router.get('/users',response_model=Document)
async def users(q:str='',role:str='',status:str='',student_status:str='',page:int=Query(1,ge=1),user=Depends(admin_user)):
    where={}
    if q: where['$or']=[{key:{'$regex':re.escape(q[:100]),'$options':'i'}} for key in ['name','email','phone','krc']]
    if role: where['role']=role
    if status: where['status']=status
    if student_status: where['student_status']=student_status
    return {'items':await db.users.find(where,{'_id':0,'password_hash':0}).sort('created_at',-1).skip((page-1)*15).limit(15).to_list(15),'total':await db.users.count_documents(where),'page':page}

@router.patch('/users/{user_id}',response_model=Document)
async def edit_user(user_id:str,data:UserEdit,user=Depends(admin_user)):
    target=await db.users.find_one({'id':user_id},{'_id':0,'password_hash':0})
    if not target: raise HTTPException(404,'المستخدم غير موجود')
    if target['role']=='admin' and (data.role or (data.status and data.status!='active')): raise HTTPException(403,'لا يمكن تغيير دور المدير أو تعطيله')
    update=data.model_dump(exclude_none=True,exclude={'student_decision'})
    if 'krc' in update:
        update['krc']=update['krc'].strip().upper()
        if not re.fullmatch(r'KRC[A-Z0-9-]{1,27}',update['krc']):raise HTTPException(422,'رقم كورا غير صحيح')
    if 'phone' in update:update['phone']=normalized_phone(update['phone'])
    if 'email' in update:update['email']=str(update['email']).lower()
    if data.student_decision:
        if target['role'] not in ('visitor','student'): raise HTTPException(422,'هذا الحساب غير مؤهل لاعتماد الطالب')
        if not target.get('krc') or not target.get('registration_date') or not target.get('university') or not target.get('research_field'): raise HTTPException(422,'بيانات الطالب غير مكتملة')
        update['student_status']=data.student_decision
        update['role']='student' if data.student_decision=='approved' else 'visitor'
    if data.role: update['student_status']='none'
    try: await db.users.update_one({'id':user_id},{'$set':update})
    except DuplicateKeyError: raise HTTPException(409,'البريد أو الهاتف أو رقم كورا مستخدم بالفعل')
    if data.status and data.status!='active':await db.sessions.delete_many({'user_id':user_id})
    await audit(user['id'],'user_updated',user_id,', '.join(f'{key}={value}' if key in ('status','role','student_status') else key for key,value in update.items()))
    return await db.users.find_one({'id':user_id},{'_id':0,'password_hash':0})

@router.post('/employees',response_model=Document)
async def create_employee(data:Register,user=Depends(admin_user)):
    row={**profile_data(data),'id':uid(),'email':str(data.email).lower(),'role':'employee','status':'active','student_status':'none','avatar_id':None,'created_at':stamp()}
    try:await db.users.insert_one({**row,'password_hash':await asyncio.to_thread(hash_password,data.password)})
    except DuplicateKeyError:raise HTTPException(409,'البريد أو الهاتف مستخدم بالفعل')
    await audit(user['id'],'employee_created',row['id'])
    return row

@router.put('/settings',response_model=Document)
async def settings(data:SettingsInput,user=Depends(admin_user)):
    row=data.model_dump();row['currency']=row['currency'].strip().upper()
    if row['currency'] and not re.fullmatch('[A-Z]{3}',row['currency']):raise HTTPException(422,'أدخل رمز العملة المكوّن من ثلاثة أحرف')
    if row['contact_email']:
        try:TypeAdapter(EmailStr).validate_python(row['contact_email'])
        except ValueError:raise HTTPException(422,'بريد التواصل غير صحيح')
    old=await db.settings.find_one({'id':'site'},{'_id':0})
    if old['currency']!=row['currency']:
        await db.courses.update_many({'published':True},{'$set':{'published':False}})
    await db.settings.update_one({'id':'site'},{'$set':row})
    await audit(user['id'],'settings_updated','site','currency changed; courses unpublished' if old['currency']!=row['currency'] else '')
    return {**row,'id':'site'}

@router.get('/audit',response_model=Document)
async def audit_list(q:str='',page:int=Query(1,ge=1),user=Depends(admin_user)):
    where={'$or':[{k:{'$regex':re.escape(q[:100]),'$options':'i'}} for k in ['action','target','details']]} if q else {}
    items=await db.audit.find(where,{'_id':0}).sort('created_at',-1).skip((page-1)*25).limit(25).to_list(25)
    for row in items:
        actor=await db.users.find_one({'id':row['user_id']},{'_id':0,'name':1})
        row['user_name']=actor['name'] if actor else 'النظام'
    return {'items':items,'total':await db.audit.count_documents(where),'page':page}