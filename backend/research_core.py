from datetime import timedelta
from fastapi import HTTPException
from pymongo import ReturnDocument
from core import db, uid, stamp, audit, now

SERVICE_NAMES={'data_collection':'جمع البيانات','postgraduate':'الدراسات العليا','graduation':'مشروع تخرج','analysis':'تحليل البيانات','other':'دعم بحثي'}
WORK_STATES=['draft','waiting_quote','pending_accept','available','claimed','in_progress','ready_payment','delivered','revision_requested','completed','cancelled']
EMPLOYEE_WORK_EVENTS={'created','submitted','details_updated','attachment_added','attachment_removed','claim','return','start','result_uploaded','deliver','revision','complete','reopen_assignment'}
CANCELLATION_EVENTS={'cancel','approve_cancel','reject_cancel'}

def employee_events(events):
    """Allowlist operational events; never expose settlement notes, including legacy rows."""
    safe=[]
    for item in events:
        action=item.get('action')
        cancellation=action in CANCELLATION_EVENTS
        if not cancellation and (item.get('financial') or action not in EMPLOYEE_WORK_EVENTS):continue
        visible={key:item.get(key,'') for key in ('id','action','actor_label','created_at')}
        visible['note']='' if cancellation else item.get('note','')
        safe.append(visible)
    return safe

async def get_research(rid):
    row=await db.research_requests.find_one({'id':rid},{'_id':0})
    if not row: raise HTTPException(404,'الطلب البحثي غير موجود')
    return row

def event(user, action, note='', financial=False):
    role={'admin':'الإدارة','employee':'الموظف','student':'صاحب الطلب','visitor':'صاحب الطلب'}[user['role']]
    return {'id':uid(),'action':action,'note':note,'actor_id':user['id'],'actor_label':role,'created_at':stamp(),'financial':financial}

async def change_request(row, user, updates, action, note='', financial=False, extra_filter=None):
    update={'$set':{**updates,'updated_at':stamp()},'$inc':{'version':1},'$push':{'events':event(user,action,note,financial)}}
    result=await db.research_requests.find_one_and_update({'id':row['id'],'version':row['version'],**(extra_filter or {})},update,projection={'_id':0},return_document=ReturnDocument.AFTER)
    if not result: raise HTTPException(409,'تغيّر الطلب منذ فتح الصفحة. حدّث الصفحة وحاول مجددًا')
    await audit(user['id'],'research_'+action,row['id'],note[:300])
    return result

def is_owner(row,user): return row['owner_id']==user['id'] and user['role'] in ('student','visitor')
def is_assigned(row,user): return user['role']=='employee' and row.get('assigned_to')==user['id'] and row['status']!='cancelled'
def is_paid(row): return bool(row.get('accepted_quote') and row['paid_minor']>=row['accepted_quote']['amount_minor'])

def require_owner(row,user):
    if not is_owner(row,user):raise HTTPException(403,'هذا الإجراء متاح لصاحب الطلب فقط')

def require_worker(row,user):
    if not is_assigned(row,user):raise HTTPException(403,'يجب أن يكون الطلب مسندًا إليك')

async def visible_research(row,user,summary=False):
    admin=user['role']=='admin'; owner=is_owner(row,user); worker=is_assigned(row,user)
    available=user['role']=='employee' and row['status']=='available' and not row.get('cancel_requested')
    if not (admin or owner or worker or available):raise HTTPException(404,'الطلب غير متاح لك')
    if user['role']=='employee':
        base={k:row[k] for k in ('id','reference','service_type','research_field','status','created_at','updated_at','revision_count')}
        base['title']=row['title'] if worker else SERVICE_NAMES[row['service_type']]
        base['assigned_to_me']=worker
        if worker and not summary:
            base.update(description=row['description'],input_files=row['input_files'],result_files=row['result_files'],released_file_ids=row['released_file_ids'],revision_note=row.get('revision_note',''),cancel_requested=row.get('cancel_requested',False))
            base['scope']=row['accepted_quote']['scope'];base['delivery_days']=row['accepted_quote']['delivery_days'];base['due_at']=row.get('due_at')
            base['events']=employee_events(row['events'])
        return base
    result={k:v for k,v in row.items() if k not in ('_id','version')}
    if not admin:
        result.pop('assigned_to',None)
        result['events']=[{k:v for k,v in ev.items() if k not in ('actor_id','financial')} for ev in row['events']]
        for receipt in result['receipts']:receipt.pop('reviewer_id',None)
        released=set(row['released_file_ids'])
        result['result_files']=[f for f in row['result_files'] if is_paid(row) and f['id'] in released]
        result['results_locked']=bool(row['result_files']) and not is_paid(row)
        result.pop('released_file_ids',None)
    if summary:
        for key in ('description','events','quotes','input_files','result_files','receipts','released_file_ids'):
            result.pop(key,None)
    if admin:
        result['owner']=await db.users.find_one({'id':row['owner_id']},{'_id':0,'name':1,'email':1,'role':1})
        if row.get('assigned_to'):
            worker_user=await db.users.find_one({'id':row['assigned_to']},{'_id':0,'name':1})
            result['employee_name']=worker_user['name'] if worker_user else 'حساب غير متاح'
    return result

async def authorize_research_upload(purpose,rid,user):
    row=await get_research(rid)
    if purpose=='research_input':
        require_owner(row,user)
        if row['status'] not in ('draft','waiting_quote'):raise HTTPException(409,'لا يمكن تغيير المرفقات بعد إرسال عرض السعر')
        if len(row['input_files'])>=30:raise HTTPException(422,'بلغت الحد الأقصى لمرفقات هذا الطلب')
    elif purpose=='research_result':
        require_worker(row,user)
        if row['status'] not in ('claimed','in_progress','revision_requested'):raise HTTPException(409,'الطلب ليس في مرحلة معالجة الملفات')
        if len(row['result_files'])>=30:raise HTTPException(422,'بلغت الحد الأقصى لنسخ النتائج')
    else:
        require_owner(row,user)
        if not row.get('accepted_quote') or is_paid(row) or row['status']=='cancelled' or row['payment_status']=='pending':
            raise HTTPException(409,'لا يمكن رفع إيصال لهذا الطلب في حالته الحالية')
    return row

async def attach_research_file(file,user):
    row=await authorize_research_upload(file['purpose'],file['context_id'],user)
    if file['purpose']=='research_receipt':return
    field='input_files' if file['purpose']=='research_input' else 'result_files'
    item={k:file[k] for k in ('id','original_filename','content_type','size','created_at')}
    item['revision']=row['revision_count']
    await change_request(row,user,{field:[*row[field],item]},'attachment_added' if field=='input_files' else 'result_uploaded')

async def research_file_allowed(file,user):
    row=await db.research_requests.find_one({'id':file['context_id']},{'_id':0})
    if not row:return False
    if user['role']=='admin':return True
    if row['status']=='cancelled':return file['purpose']=='research_receipt' and is_owner(row,user)
    if file['purpose']=='research_receipt':return is_owner(row,user)
    if file['purpose']=='research_input':return (is_owner(row,user) or is_assigned(row,user)) and any(f['id']==file['id'] for f in row['input_files'])
    registered=any(f['id']==file['id'] for f in row['result_files'])
    return registered and (is_assigned(row,user) or (is_owner(row,user) and is_paid(row) and file['id'] in row['released_file_ids']))