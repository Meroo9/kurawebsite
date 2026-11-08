import re
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from core import db,uid,stamp,current_user,admin_user,Document,audit,limit
from research_models import ResearchInput,QuoteInput,QuoteDecision,minor_amount,discounted_amount
from research_core import get_research,visible_research,change_request,is_owner,require_owner,event

router=APIRouter(tags=['research'])

@router.post('/research',response_model=Document)
async def create_research(data:ResearchInput,request:Request,user=Depends(current_user)):
    if user['role'] not in ('student','visitor'):raise HTTPException(403,'إنشاء الطلبات متاح للطلاب والزوار المسجلين')
    await limit(request,'research-create',20)
    rid=uid()
    row={**data.model_dump(),'id':rid,'reference':'KR-'+rid[:8].upper(),'owner_id':user['id'],'status':'draft','payment_status':'unquoted','paid_minor':0,'assigned_to':None,'ever_claimed':False,'cancel_requested':False,'revision_count':0,'quotes':[],'quote':None,'accepted_quote':None,'input_files':[],'result_files':[],'released_file_ids':[],'receipts':[],'events':[event(user,'created')],'version':0,'created_at':stamp(),'updated_at':stamp()}
    await db.research_requests.insert_one(row.copy())
    await audit(user['id'],'research_created',rid)
    return await visible_research(row,user)

@router.get('/research',response_model=Document)
async def list_research(q:str='',status:str='',scope:str='mine',payment_status:str='',page:int=Query(1,ge=1),user=Depends(current_user)):
    if user['role']=='admin':where={'status':{'$ne':'draft'}}
    elif user['role']=='employee':where={'status':'available','cancel_requested':False} if scope=='available' else {'assigned_to':user['id'],'status':{'$ne':'cancelled'}}
    else:where={'owner_id':user['id']}
    if status:where={'$and':[where,{'status':status}]}
    if q:
        keys=['reference','research_field'] if user['role']=='employee' and scope=='available' else ['reference','title','research_field']
        where={'$and':[where,{'$or':[{k:{'$regex':re.escape(q[:100]),'$options':'i'}} for k in keys]}]}
    if payment_status and user['role']!='employee':where={'$and':[where,{'payment_status':payment_status}]}
    items=await db.research_requests.find(where,{'_id':0}).sort('created_at',-1).skip((page-1)*12).limit(12).to_list(12)
    return {'items':[await visible_research(row,user,True) for row in items],'total':await db.research_requests.count_documents(where),'page':page}

@router.get('/research/{rid}',response_model=Document)
async def detail(rid:str,user=Depends(current_user)):
    return await visible_research(await get_research(rid),user)

@router.post('/research/{rid}/submit',response_model=Document)
async def submit(rid:str,user=Depends(current_user)):
    row=await get_research(rid);require_owner(row,user)
    if row['status']!='draft':raise HTTPException(409,'تم إرسال الطلب مسبقًا')
    updated=await change_request(row,user,{'status':'waiting_quote'},'submitted')
    return await visible_research(updated,user)

@router.put('/research/{rid}',response_model=Document)
async def edit(rid:str,data:ResearchInput,user=Depends(current_user)):
    row=await get_research(rid);require_owner(row,user)
    if row['status'] not in ('draft','waiting_quote'):raise HTTPException(409,'لا يمكن تعديل التفاصيل بعد إرسال عرض السعر')
    return await visible_research(await change_request(row,user,data.model_dump(),'details_updated'),user)

@router.delete('/research/{rid}/attachments/{fid}')
async def remove_attachment(rid:str,fid:str,user=Depends(current_user)):
    row=await get_research(rid);require_owner(row,user)
    if row['status'] not in ('draft','waiting_quote'):raise HTTPException(409,'لا يمكن حذف المرفق بعد إرسال عرض السعر')
    if not any(f['id']==fid for f in row['input_files']):raise HTTPException(404,'المرفق غير موجود')
    await change_request(row,user,{'input_files':[f for f in row['input_files'] if f['id']!=fid]},'attachment_removed')
    await db.files.update_one({'id':fid},{'$set':{'is_deleted':True}})
    return {'success':True}

@router.post('/research/{rid}/quote',response_model=Document)
async def quote_request(rid:str,data:QuoteInput,user=Depends(admin_user)):
    row=await get_research(rid)
    if row['status'] not in ('waiting_quote','pending_accept'):raise HTTPException(409,'لا يمكن تغيير عرض السعر بعد قبوله وبدء العمل')
    settings=await db.settings.find_one({'id':'site'},{'_id':0})
    if not settings['currency'] or not settings['payment_instructions'].strip():raise HTTPException(422,'حدد العملة وتعليمات الدفع في إعدادات المركز أولًا')
    owner=await db.users.find_one({'id':row['owner_id']},{'_id':0,'role':1,'status':1})
    if not owner or owner['status']!='active':raise HTTPException(409,'حساب صاحب الطلب غير نشط')
    original=minor_amount(data.amount);discount=15 if owner['role']=='student' else 0
    quote={'id':uid(),'original_minor':original,'discount_percent':discount,'amount_minor':discounted_amount(original,discount),'currency':settings['currency'],'payment_instructions':settings['payment_instructions'],'scope':data.scope.strip(),'delivery_days':data.delivery_days,'revision_limit':1,'status':'pending','created_at':stamp(),'approved_for_work':True}
    if len(quote['scope'])<10:raise HTTPException(422,'وضح النطاق المتفق عليه')
    history=[*row['quotes']]
    if row.get('quote'):history.append({**row['quote'],'status':'superseded'})
    updated=await change_request(row,user,{'quote':quote,'quotes':history,'status':'pending_accept','payment_status':'unaccepted'},'quote_sent',financial=True)
    return await visible_research(updated,user)

@router.post('/research/{rid}/quote-decision',response_model=Document)
async def quote_decision(rid:str,data:QuoteDecision,user=Depends(current_user)):
    row=await get_research(rid);require_owner(row,user)
    if row['status']!='pending_accept' or not row['quote'] or row['quote']['id']!=data.quote_id:raise HTTPException(409,'هذا العرض لم يعد صالحًا؛ حدّث الصفحة')
    quote=row['quote']
    if data.decision=='accepted':
        discount=15 if user['role']=='student' else 0
        if discount!=quote['discount_percent']:raise HTTPException(409,'تغيّرت أهلية خصم الطالب. يرجى طلب تحديث العرض من الإدارة قبل قبوله')
        accepted={**quote,'status':'accepted','accepted_at':stamp()}
        updates={'status':'available','quote':accepted,'accepted_quote':accepted,'payment_status':'unpaid'}
    else:
        if not data.reason.strip():raise HTTPException(422,'يرجى توضيح سبب رفض العرض')
        rejected={**quote,'status':'rejected','reason':data.reason.strip()}
        updates={'status':'waiting_quote','quotes':[*row['quotes'],rejected],'quote':None,'payment_status':'unquoted'}
    updated=await change_request(row,user,updates,'quote_'+data.decision,data.reason.strip(),True)
    return await visible_research(updated,user)