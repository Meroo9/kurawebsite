import re
from decimal import Decimal, InvalidOperation
from fastapi import APIRouter, Depends, HTTPException, Query
from core import db, uid, stamp, admin_user, optional_user, course_access, audit, Document
from schemas import CourseInput, LectureInput, CategoryInput

router = APIRouter(tags=['courses'])

@router.get('/site', response_model=Document)
async def site(): return await db.settings.find_one({'id': 'site'}, {'_id': 0})

@router.get('/categories', response_model=list[Document])
async def categories(): return await db.categories.find({}, {'_id': 0}).sort('name', 1).to_list(200)

@router.get('/courses', response_model=Document)
async def courses(q: str = '', category: str = '', page: int = Query(1, ge=1), user=Depends(optional_user)):
    where = {'published': True, 'deleted': {'$ne': True}}
    if q: where['title'] = {'$regex': re.escape(q[:100]), '$options': 'i'}
    if category: where['category_id'] = category
    items = await db.courses.find(where, {'_id': 0}).sort('created_at', -1).skip((page-1)*12).limit(12).to_list(12)
    for item in items:
        item['has_access'] = await course_access(user, item)
        item['lecture_count'] = await db.lectures.count_documents({'course_id': item['id'], 'deleted': {'$ne': True}})
    return {'items': items, 'total': await db.courses.count_documents(where), 'page': page}

@router.get('/courses/{course_id}', response_model=Document)
async def course_detail(course_id: str, user=Depends(optional_user)):
    item = await db.courses.find_one({'id': course_id, 'deleted': {'$ne': True}}, {'_id': 0})
    if not item: raise HTTPException(404, 'الكورس غير موجود')
    access = await course_access(user, item)
    if not item['published'] and not access: raise HTTPException(404, 'الكورس غير موجود')
    item['has_access'] = access
    item['lectures'] = await db.lectures.find({'course_id': course_id, 'deleted': {'$ne': True}}, {'_id': 0}).sort('order', 1).to_list(500)
    if not access:
        for lecture in item['lectures']: lecture.pop('file_id', None)
    return item

@router.get('/admin/courses', response_model=Document)
async def admin_courses(q: str = '', page: int = Query(1, ge=1), user=Depends(admin_user)):
    where = {'deleted': {'$ne': True}}
    if q: where['title'] = {'$regex': re.escape(q[:100]), '$options': 'i'}
    return {'items': await db.courses.find(where, {'_id': 0}).sort('created_at', -1).skip((page-1)*15).limit(15).to_list(15), 'total': await db.courses.count_documents(where), 'page': page}

async def validated_course(data):
    if not await db.categories.find_one({'id': data.category_id}): raise HTTPException(422, 'اختر تصنيفًا صحيحًا')
    settings = await db.settings.find_one({'id': 'site'}, {'_id': 0})
    try:
        amount = Decimal(data.price)
        if not amount.is_finite() or amount < 0 or amount > 10000000 or amount.as_tuple().exponent < -2: raise InvalidOperation()
        minor = int(amount * 100)
    except (InvalidOperation, ValueError): raise HTTPException(422, 'أدخل سعرًا صحيحًا حتى منزلتين عشريتين')
    if data.published and (not settings['currency'] or (minor > 0 and not settings['payment_instructions'].strip())):
        raise HTTPException(422, 'حدد العملة وتعليمات الدفع في الإعدادات قبل النشر')
    return {**data.model_dump(exclude={'price'}), 'price_minor': minor, 'currency': settings['currency']}

@router.post('/admin/courses', response_model=Document)
async def create_course(data: CourseInput, user=Depends(admin_user)):
    row = {**await validated_course(data), 'id': uid(), 'created_at': stamp(), 'deleted': False}
    await db.courses.insert_one(row.copy())
    await audit(user['id'], 'course_created', row['id'])
    return row

@router.put('/admin/courses/{cid}', response_model=Document)
async def edit_course(cid: str, data: CourseInput, user=Depends(admin_user)):
    row = await validated_course(data)
    result = await db.courses.update_one({'id': cid, 'deleted': {'$ne': True}}, {'$set': row})
    if not result.matched_count: raise HTTPException(404, 'الكورس غير موجود')
    await audit(user['id'], 'course_updated', cid)
    return await db.courses.find_one({'id': cid}, {'_id': 0})

@router.delete('/admin/courses/{cid}')
async def delete_course(cid: str, user=Depends(admin_user)):
    result = await db.courses.update_one({'id': cid, 'deleted': {'$ne': True}}, {'$set': {'deleted': True, 'published': False}})
    if not result.matched_count: raise HTTPException(404, 'الكورس غير موجود أو تمت أرشفته بالفعل')
    await audit(user['id'], 'course_archived', cid)
    return {'success': True}

@router.post('/admin/courses/{cid}/lectures', response_model=Document)
async def add_lecture(cid: str, data: LectureInput, user=Depends(admin_user)):
    if not await db.courses.find_one({'id': cid, 'deleted': {'$ne': True}}): raise HTTPException(404, 'الكورس غير موجود')
    if not await db.files.find_one({'id': data.file_id, 'purpose': 'lecture', 'context_id': cid, 'is_deleted': False}): raise HTTPException(422, 'ملف المحاضرة غير صحيح')
    row = {**data.model_dump(), 'id': uid(), 'course_id': cid, 'deleted': False, 'created_at': stamp()}
    await db.lectures.insert_one(row.copy())
    await audit(user['id'], 'lecture_created', row['id'])
    return row

@router.put('/admin/lectures/{lid}', response_model=Document)
async def edit_lecture(lid: str, data: LectureInput, user=Depends(admin_user)):
    row = await db.lectures.find_one({'id': lid, 'deleted': False}, {'_id': 0})
    if not row: raise HTTPException(404, 'المحاضرة غير موجودة')
    if not await db.files.find_one({'id': data.file_id, 'purpose': 'lecture', 'context_id': row['course_id'], 'is_deleted': False}): raise HTTPException(422, 'ملف غير صحيح')
    await db.lectures.update_one({'id': lid}, {'$set': data.model_dump()})
    await audit(user['id'], 'lecture_updated', lid)
    return {**row, **data.model_dump()}

@router.delete('/admin/lectures/{lid}')
async def remove_lecture(lid: str, user=Depends(admin_user)):
    result = await db.lectures.update_one({'id': lid, 'deleted': {'$ne': True}}, {'$set': {'deleted': True}})
    if not result.matched_count: raise HTTPException(404, 'المحاضرة غير موجودة أو تم حذفها بالفعل')
    await audit(user['id'], 'lecture_archived', lid)
    return {'success': True}

@router.post('/admin/categories', response_model=Document)
async def add_category(data: CategoryInput, user=Depends(admin_user)):
    row = {'id': uid(), 'name': data.name.strip()}
    await db.categories.insert_one(row.copy())
    await audit(user['id'], 'category_created', row['id'])
    return row

@router.put('/admin/categories/{cid}')
async def edit_category(cid: str, data: CategoryInput, user=Depends(admin_user)):
    result = await db.categories.update_one({'id': cid}, {'$set': {'name': data.name.strip()}})
    if not result.matched_count: raise HTTPException(404, 'التصنيف غير موجود')
    await audit(user['id'], 'category_updated', cid)
    return {'success': True}

@router.delete('/admin/categories/{cid}')
async def remove_category(cid: str, user=Depends(admin_user)):
    if await db.courses.count_documents({'category_id': cid, 'deleted': {'$ne': True}}): raise HTTPException(409, 'انقل كورسات هذا التصنيف أولًا')
    result = await db.categories.delete_one({'id': cid})
    if not result.deleted_count: raise HTTPException(404, 'التصنيف غير موجود')
    await audit(user['id'], 'category_deleted', cid)
    return {'success': True}