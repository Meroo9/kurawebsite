import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.cors import CORSMiddleware
from core import db, client, ORIGIN
from auth import router as auth_router
from catalog import router as catalog_router
from commerce import router as commerce_router
from media import router as media_router
from administration import router as admin_router

@asynccontextmanager
async def lifespan(app):
    await db.users.create_index('email', unique=True)
    await db.users.create_index('phone', unique=True)
    await db.users.create_index('krc', unique=True, partialFilterExpression={'krc': {'$type': 'string'}})
    await db.sessions.create_index('expires_at', expireAfterSeconds=0)
    await db.rate_limits.create_index('expires_at', expireAfterSeconds=0)
    await db.reset_tokens.create_index('expires_at', expireAfterSeconds=0)
    await db.purchases.create_index([('user_id', 1), ('course_id', 1)], unique=True)
    await db.settings.update_one({'id': 'site'}, {'$setOnInsert': {
        'id': 'site', 'currency': '', 'payment_instructions': '', 'contact_email': '',
        'contact_phone': '', 'address': '', 'about': 'مركز كورا للأبحاث والتعليم الطبي. مساحة تجمع التعلم الطبي والدعم البحثي، وتضع المعرفة في متناولك.',
        'services_text': 'كورسات ومحاضرات طبية، ومسارات للدعم البحثي وجمع البيانات ومشاريع التخرج.',
        'hero_description': 'مساحة تجمع المعرفة الطبية والبحث العلمي. طوّر مهاراتك مع الكورسات والمحاضرات، وابدأ رحلتك نحو آفاق أوسع من المعرفة.'
    }}, upsert=True)
    for name, cid in [('التعليم الطبي', 'medical'), ('البحث العلمي', 'research'), ('الإحصاء وتحليل البيانات', 'statistics')]:
        await db.categories.update_one({'id': cid}, {'$setOnInsert': {'id': cid, 'name': name}}, upsert=True)
    yield
    client.close()

app = FastAPI(title='KURA Research', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=[ORIGIN], allow_credentials=True, allow_methods=['GET','POST','PUT','DELETE','PATCH'], allow_headers=['Content-Type','Range','X-Kura-Request'])

@app.middleware('http')
async def security_headers(request: Request, call_next):
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.headers.get('origin') not in (None, ORIGIN):
        return JSONResponse({'detail': 'مصدر الطلب غير مسموح'}, status_code=403)
    # The embedded preview proxy can rewrite SameSite cookies. Require a non-simple
    # header on every authenticated mutation, in addition to strict Origin/CORS.
    # A cross-origin HTML form cannot supply it, and CORS denies hostile preflights.
    if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.cookies.get('kura_session') and request.headers.get('X-Kura-Request') != '1':
        return JSONResponse({'detail': 'تعذر التحقق من مصدر الطلب. أعد تحميل الصفحة'}, status_code=403)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    return JSONResponse({'detail': 'يرجى مراجعة الحقول المطلوبة وصحة البيانات المدخلة'}, status_code=422)

for router in (auth_router, catalog_router, commerce_router, media_router, admin_router):
    app.include_router(router, prefix='/api')

@app.get('/api/health')
async def health():
    await db.command('ping')
    return {'status': 'ok', 'phase': 1}

logging.basicConfig(level=logging.INFO)