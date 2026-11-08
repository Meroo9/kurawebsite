import os, asyncio, io, zipfile, re, tempfile
from pathlib import Path
from urllib.parse import quote
import httpx
from PIL import Image, UnidentifiedImageError
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import Response, StreamingResponse
from pypdf import PdfReader
from core import db, uid, stamp, current_user, course_access, audit, Document

router = APIRouter(tags=['private files'])
STORAGE_BASE = (os.environ.get('INTEGRATION_PROXY_URL') or '').strip() or 'https://integrations.emergentagent.com'
STORAGE_URL = STORAGE_BASE.rstrip('/') + '/objstore/api/v1/storage'
storage_key = None
storage_lock = asyncio.Lock()

async def init_storage(force=False):
    global storage_key
    async with storage_lock:
        if storage_key and not force: return storage_key
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f'{STORAGE_URL}/init', json={'emergent_key': os.environ['EMERGENT_LLM_KEY']})
        response.raise_for_status()
        storage_key = response.json()['storage_key']
        return storage_key

async def storage_request(method, path, **kwargs):
    try:
        key = await init_storage()
        content_headers = kwargs.pop('headers', {})
        async with httpx.AsyncClient(timeout=180) as client:
            response = await client.request(method, f'{STORAGE_URL}/objects/{path}', headers={'X-Storage-Key': key, **content_headers}, **kwargs)
            if response.status_code == 404:
                key = await init_storage(force=True)
                response = await client.request(method, f'{STORAGE_URL}/objects/{path}', headers={'X-Storage-Key': key, **content_headers}, **kwargs)
            response.raise_for_status()
        return response
    except (httpx.HTTPError, KeyError):
        raise HTTPException(503, 'تخزين الملفات غير متاح مؤقتًا. يرجى المحاولة لاحقًا')

TYPES = {'pdf':'application/pdf','png':'image/png','jpg':'image/jpeg','jpeg':'image/jpeg','webp':'image/webp','mp4':'video/mp4','docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','pptx':'application/vnd.openxmlformats-officedocument.presentationml.presentation','txt':'text/plain','csv':'text/csv'}

async def storage_download(path):
    """Stream into a bounded spool instead of retaining a whole video in RAM."""
    spool = tempfile.SpooledTemporaryFile(max_size=8*1024*1024)
    try:
        for attempt in range(2):
            key = await init_storage(force=bool(attempt))
            async with httpx.AsyncClient(timeout=180) as client:
                async with client.stream('GET', f'{STORAGE_URL}/objects/{path}', headers={'X-Storage-Key':key}) as response:
                    if response.status_code == 404 and attempt == 0: continue
                    response.raise_for_status()
                    size = 0
                    async for chunk in response.aiter_bytes(64*1024):
                        size += len(chunk)
                        if size > 100*1024*1024: raise ValueError('File exceeds upload policy')
                        await asyncio.to_thread(spool.write, chunk)
                    spool.seek(0)
                    return spool, size
    except Exception:
        spool.close()
        raise HTTPException(503, 'تعذر تحميل الملف حاليًا. يرجى المحاولة مجددًا')

def stream_spool(spool, length):
    try:
        while length > 0:
            chunk=spool.read(min(64*1024,length))
            if not chunk: break
            length -= len(chunk)
            yield chunk
    finally:
        spool.close()

def validate_file(data, ext):
    if ext in ('png','jpg','jpeg','webp'):
        try:
            image = Image.open(io.BytesIO(data)); image.verify()
            if image.width * image.height > 30000000: raise ValueError()
            if image.format != {'png':'PNG','jpg':'JPEG','jpeg':'JPEG','webp':'WEBP'}[ext]: raise ValueError()
        except Exception: raise HTTPException(422, 'ملف الصورة غير صالح')
    elif ext == 'pdf':
        try:
            if not data.startswith(b'%PDF-'): raise ValueError()
            reader = PdfReader(io.BytesIO(data), strict=True)
            if reader.is_encrypted or not len(reader.pages): raise ValueError()
            if reader.trailer['/Root'].get('/OpenAction') or reader.trailer['/Root'].get('/AA'): raise ValueError()
        except Exception: raise HTTPException(422, 'ملف PDF غير صالح أو محمي أو يحتوي إجراءات نشطة')
    elif ext == 'mp4':
        if data[4:8] != b'ftyp': raise HTTPException(422, 'ملف MP4 غير صالح')
    elif ext in ('docx','xlsx','pptx'):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                expected={'docx':'word/document.xml','xlsx':'xl/workbook.xml','pptx':'ppt/presentation.xml'}[ext]
                if expected not in archive.namelist() or any('vbaProject' in n for n in archive.namelist()): raise ValueError()
        except Exception: raise HTTPException(422, 'المستند غير صالح أو يحتوي وحدات ماكرو')
    else:
        try: data.decode('utf-8')
        except UnicodeDecodeError: raise HTTPException(422, 'يجب أن يكون الملف النصي بترميز UTF-8')

@router.post('/files', response_model=Document)
async def upload_file(file: UploadFile = File(...), purpose: str = Form(...), context_id: str = Form(''), user=Depends(current_user)):
    research_purposes=('research_input','research_result','research_receipt')
    if purpose not in ('avatar', 'receipt', 'lecture','post_image',*research_purposes): raise HTTPException(422, 'نوع الرفع غير مسموح')
    max_mb = {'avatar':5,'receipt':10,'lecture':100,'post_image':5,'research_input':25,'research_result':25,'research_receipt':10}[purpose]
    images={'jpg','jpeg','png','webp'}
    allowed = {'avatar':images,'post_image':images, 'receipt':{'pdf',*images}, 'lecture':set(TYPES),'research_input':set(TYPES)-{'mp4'},'research_result':set(TYPES)-{'mp4'},'research_receipt':{'pdf',*images}}[purpose]
    if purpose=='post_image' and user['role']!='admin':raise HTTPException(403,'صور المنشورات متاحة للإدارة فقط')
    if purpose in research_purposes:
        from research_core import authorize_research_upload
        await authorize_research_upload(purpose,context_id,user)
    ext = Path(file.filename or '').suffix.lower().lstrip('.')
    if ext not in allowed: raise HTTPException(422, 'صيغة الملف غير مدعومة')
    if purpose == 'lecture':
        if user['role'] != 'admin': raise HTTPException(403, 'رفع المحاضرات متاح للإدارة فقط')
        if not await db.courses.find_one({'id': context_id, 'deleted': {'$ne': True}}): raise HTTPException(404, 'الكورس غير موجود')
    if purpose == 'receipt' and not await db.purchases.find_one({'id': context_id, 'user_id': user['id'], 'status': {'$in':['awaiting_receipt','rejected']}}):
        raise HTTPException(403, 'لا يمكن رفع إيصال لهذه العملية')
    chunks=[]; size=0
    while chunk := await file.read(1024*1024):
        size += len(chunk)
        if size > max_mb*1024*1024: raise HTTPException(413, f'الحد الأقصى للملف {max_mb} ميجابايت')
        chunks.append(chunk)
    data = b''.join(chunks)
    if not data: raise HTTPException(422, 'الملف فارغ')
    await asyncio.to_thread(validate_file, data, ext)
    fid=uid(); path=f'kura-research/uploads/{user["id"]}/{fid}.{ext}'
    response = await storage_request('PUT', path, content=data, headers={'Content-Type':TYPES[ext]})
    row={'id':fid,'storage_path':response.json()['path'],'owner_id':user['id'],'purpose':purpose,'context_id':context_id,'original_filename':Path(file.filename).name[:200],'content_type':TYPES[ext],'size':size,'is_deleted':False,'created_at':stamp()}
    await db.files.insert_one(row.copy())
    if purpose in research_purposes:
        from research_core import attach_research_file
        try:await attach_research_file(row,user)
        except HTTPException:
            await db.files.update_one({'id':fid},{'$set':{'is_deleted':True}})
            raise
    if purpose == 'avatar':
        if user.get('avatar_id'): await db.files.update_one({'id':user['avatar_id']},{'$set':{'is_deleted':True}})
        await db.users.update_one({'id':user['id']},{'$set':{'avatar_id':fid}})
    await audit(user['id'], 'file_uploaded', fid, purpose)
    return {'id':fid,'original_filename':row['original_filename'],'content_type':row['content_type'],'size':size}

async def authorized_file(fid, user):
    row = await db.files.find_one({'id':fid,'is_deleted':False}, {'_id':0})
    if not row: raise HTTPException(404, 'الملف غير متاح')
    allowed = user['role'] == 'admin'
    if row['purpose'] in ('avatar','receipt'): allowed = allowed or row['owner_id'] == user['id']
    elif row['purpose'] == 'lecture':
        lecture = await db.lectures.find_one({'file_id':fid,'deleted':False}, {'_id':0})
        course = await db.courses.find_one({'id':row['context_id'],'deleted':{'$ne':True}}, {'_id':0})
        allowed = allowed or bool(lecture and course and await course_access(user,course))
    elif row['purpose'].startswith('research_'):
        from research_core import research_file_allowed
        allowed=await research_file_allowed(row,user)
    if not allowed: raise HTTPException(403, 'ليس لديك صلاحية الوصول إلى هذا الملف')
    return row

@router.get('/files/{fid}/metadata', response_model=Document)
async def file_metadata(fid: str, user=Depends(current_user)):
    row = await authorized_file(fid, user)
    return {key:row[key] for key in ('id','original_filename','content_type','size')}

@router.get('/files/{fid}')
async def download_file(fid: str, request: Request, download: bool = False, user=Depends(current_user)):
    row = await authorized_file(fid, user)
    spool, size = await storage_download(row['storage_path'])
    await audit(user['id'], 'file_download' if download else 'file_view',fid,row['purpose'])
    # Re-check immediately before delivery in case access was revoked during storage fetch.
    active = await db.users.find_one({'id':user['id'],'status':'active'}, {'_id':0,'password_hash':0})
    if not active:
        spool.close()
        raise HTTPException(403, 'تم إيقاف الحساب')
    try:await authorized_file(fid,active)
    except HTTPException:
        spool.close()
        raise
    inline = row['content_type'] in ('application/pdf','image/png','image/jpeg','image/webp','video/mp4','text/plain')
    disposition = 'attachment' if download or not inline else 'inline'
    headers={'Content-Disposition':f"{disposition}; filename*=UTF-8''{quote(row['original_filename'])}", 'Accept-Ranges':'bytes', 'Content-Security-Policy':"sandbox"}
    range_header = request.headers.get('range')
    if range_header:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)',range_header)
        if not match or not any(match.groups()):
            spool.close()
            return Response(status_code=416,headers={'Content-Range':f'bytes */{size}'})
        start = int(match[1]) if match[1] else max(0,size-int(match[2])); end = min(int(match[2]),size-1) if match[1] and match[2] else size-1
        if start >= size or start > end:
            spool.close()
            return Response(status_code=416,headers={'Content-Range':f'bytes */{size}'})
        spool.seek(start)
        headers['Content-Range']=f'bytes {start}-{end}/{size}'
        headers['Content-Length']=str(end-start+1)
        return StreamingResponse(stream_spool(spool,end-start+1),status_code=206,media_type=row['content_type'],headers=headers)
    headers['Content-Length']=str(size)
    return StreamingResponse(stream_spool(spool,size),media_type=row['content_type'],headers=headers)