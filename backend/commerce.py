from fastapi import APIRouter, Depends, HTTPException, Query
from pymongo.errors import DuplicateKeyError
from core import db, uid, stamp, current_user, admin_user, course_access, audit, Document
from schemas import ReceiptInput, Review

router = APIRouter(tags=['purchases'])

@router.get('/my/purchases/course/{cid}', response_model=Document)
async def course_purchase(cid: str, user=Depends(current_user)):
    row = await db.purchases.find_one({'course_id': cid, 'user_id': user['id']}, {'_id': 0})
    return {'purchase': row}

@router.post('/courses/{cid}/purchase', response_model=Document)
async def purchase(cid: str, user=Depends(current_user)):
    if user['role'] not in ('visitor', 'student'): raise HTTPException(403, 'الشراء متاح لحسابات الطلاب والزوار')
    existing = await db.purchases.find_one({'course_id': cid, 'user_id': user['id']}, {'_id': 0})
    if existing: return existing
    course = await db.courses.find_one({'id': cid, 'published': True, 'deleted': {'$ne': True}}, {'_id': 0})
    if not course: raise HTTPException(404, 'الكورس غير متاح للشراء')
    if await course_access(user, course): raise HTTPException(409, 'الكورس متاح لك بالفعل')
    settings = await db.settings.find_one({'id': 'site'}, {'_id': 0})
    if not course['currency'] or not settings['payment_instructions'].strip(): raise HTTPException(409, 'تعليمات الدفع لم تُحدد بعد')
    row = {'id': uid(), 'user_id': user['id'], 'course_id': cid, 'course_title': course['title'], 'amount_minor': course['price_minor'], 'currency': course['currency'], 'payment_instructions': settings['payment_instructions'], 'status': 'awaiting_receipt', 'receipts': [], 'created_at': stamp()}
    try: await db.purchases.insert_one(row.copy())
    except DuplicateKeyError: return await db.purchases.find_one({'course_id': cid, 'user_id': user['id']}, {'_id': 0})
    await audit(user['id'], 'purchase_created', row['id'])
    return row

@router.post('/purchases/{pid}/receipt', response_model=Document)
async def submit_receipt(pid: str, data: ReceiptInput, user=Depends(current_user)):
    file = await db.files.find_one({'id': data.file_id, 'owner_id': user['id'], 'purpose': 'receipt', 'context_id': pid, 'is_deleted': False}, {'_id': 0})
    if not file: raise HTTPException(422, 'يرجى رفع إيصال صحيح')
    receipt = {'id': uid(), 'file_id': file['id'], 'status': 'pending', 'reason': '', 'submitted_at': stamp()}
    result = await db.purchases.update_one({'id': pid, 'user_id': user['id'], 'status': {'$in': ['awaiting_receipt','rejected']}, 'receipts.file_id': {'$ne': file['id']}}, {'$set': {'status': 'pending'}, '$push': {'receipts': receipt}})
    if not result.modified_count: raise HTTPException(409, 'تم إرسال الإيصال مسبقًا أو تمت مراجعة العملية')
    await audit(user['id'], 'receipt_submitted', pid)
    return await db.purchases.find_one({'id': pid}, {'_id': 0})

@router.get('/my/purchases', response_model=Document)
async def my_purchases(page: int = Query(1, ge=1), user=Depends(current_user)):
    query = {'user_id': user['id']}
    items = await db.purchases.find(query, {'_id': 0}).sort('created_at', -1).skip((page-1)*15).limit(15).to_list(15)
    totals = await db.purchases.aggregate([{'$match': query}, {'$group': {'_id': '$currency', 'paid': {'$sum': {'$cond': [{'$eq': ['$status','approved']}, '$amount_minor', 0]}}, 'remaining': {'$sum': {'$cond': [{'$ne': ['$status','approved']}, '$amount_minor', 0]}}}}]).to_list(100)
    return {'items': items, 'total': await db.purchases.count_documents(query), 'page': page, 'balances': [{'currency': r['_id'], 'paid_minor': r['paid'], 'remaining_minor': r['remaining']} for r in totals]}

@router.get('/my/courses', response_model=list[Document])
async def my_courses(user=Depends(current_user)):
    purchases = await db.purchases.find({'user_id': user['id'], 'status': 'approved'}, {'_id': 0, 'course_id': 1}).to_list(10000)
    options = [{'id': {'$in': [p['course_id'] for p in purchases]}}, {'published': True, 'price_minor': 0}]
    if user['role'] == 'student': options.append({'published': True, 'free_for_students': True})
    # Compact compatibility summary; the complete searchable catalog is /my/library.
    return await db.courses.find({'deleted': {'$ne': True}, '$or': options}, {'_id': 0}).sort('created_at', -1).limit(3).to_list(3)

@router.get('/my/library', response_model=Document)
async def library(q: str = '', category: str = '', page: int = Query(1,ge=1), user=Depends(current_user)):
    import re
    pipeline = [{'$match': {'deleted': {'$ne': True}}}, {'$lookup': {
        'from': 'purchases', 'let': {'course': '$id'},
        'pipeline': [{'$match': {'user_id': user['id'], 'status':'approved', '$expr': {'$eq':['$course_id','$$course']}}}, {'$project': {'_id':0,'id':1}}], 'as':'entitlements'
    }}]
    access=[{'entitlements.0': {'$exists':True}}, {'published':True,'price_minor':0}]
    if user['role']=='student': access.append({'published':True,'free_for_students':True})
    where={'$or':access}
    if q: where['title']={'$regex':re.escape(q[:100]),'$options':'i'}
    if category: where['category_id']=category
    pipeline += [{'$match':where},{'$sort':{'created_at':-1}},{'$facet': {'items':[{'$skip':(page-1)*12},{'$limit':12},{'$project':{'_id':0,'entitlements':0}}], 'count':[{'$count':'total'}]}}]
    result=(await db.courses.aggregate(pipeline).to_list(1))[0]
    return {'items':result['items'],'total':result['count'][0]['total'] if result['count'] else 0,'page':page}

@router.get('/admin/purchases', response_model=Document)
async def admin_purchases(status: str = '', q: str = '', page: int = Query(1, ge=1), user=Depends(admin_user)):
    import re
    query = {}
    if status: query['status'] = status
    if q: query['course_title'] = {'$regex': re.escape(q[:100]), '$options': 'i'}
    items = await db.purchases.find(query, {'_id': 0}).sort('created_at', -1).skip((page-1)*15).limit(15).to_list(15)
    for row in items:
        row['user'] = await db.users.find_one({'id': row['user_id']}, {'_id': 0, 'name': 1, 'email': 1})
    return {'items': items, 'total': await db.purchases.count_documents(query), 'page': page}

@router.post('/admin/purchases/{pid}/review')
async def review(pid: str, data: Review, user=Depends(admin_user)):
    if data.decision == 'rejected' and not data.reason.strip(): raise HTTPException(422, 'يرجى توضيح سبب الرفض')
    purchase = await db.purchases.find_one({'id': pid, 'status': 'pending'}, {'_id': 0})
    if not purchase: raise HTTPException(409, 'العملية ليست قيد المراجعة')
    receipt_id = purchase['receipts'][-1]['id']
    result = await db.purchases.update_one({'id': pid, 'status': 'pending', 'receipts.id': receipt_id}, {'$set': {'status': data.decision, 'receipts.$.status': data.decision, 'receipts.$.reason': data.reason.strip(), 'receipts.$.reviewed_at': stamp(), 'receipts.$.reviewer_id': user['id']}})
    if not result.modified_count: raise HTTPException(409, 'تمت مراجعة هذا الإيصال بالفعل')
    await audit(user['id'], f'receipt_{data.decision}', pid, data.reason)
    return {'success': True}