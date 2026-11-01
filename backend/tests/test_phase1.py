# Phase 1 regression: isolated accounts, catalog, private storage, purchases and reset email.
import os, sys, json, secrets, io, asyncio
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest, requests
from dotenv import load_dotenv
from pymongo import MongoClient
from PIL import Image

load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')
BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
sys.path.insert(0, '/app/backend')
from core import digest

@pytest.fixture(scope='session')
def ctx():
    mongo = MongoClient(os.environ['MONGO_URL'])
    db = mongo[os.environ['DB_NAME']]
    tag = 'TEST_' + secrets.token_hex(4)
    password = secrets.token_urlsafe(18)
    c = {'db':db,'tag':tag,'password':password,'accounts':{},'ids':{},'original':db.settings.find_one({'id':'site'},{'_id':0})}
    for i, name in enumerate(['admin','visitor','pending','other','employee']):
        session = requests.Session()
        session.headers['X-Kura-Request']='1'
        data = {'name':tag+' '+name,'email':tag.lower()+name+'@example.com','phone':'+1999'+str(secrets.randbelow(9000000)+1000000),'password':password,'role':'admin'}
        if name == 'pending': data.update(is_student=True,krc='KRC'+tag[5:],university='TEST university',research_field='TEST medicine',registration_date='2025-01-01')
        r=session.post(BASE+'/api/auth/register',json=data,timeout=60)
        assert r.status_code == 200, r.text
        assert r.json()['role']=='visitor'
        c['accounts'][name]={'session':session,'user':r.json(),'email':data['email']}
    db.users.update_one({'id':c['accounts']['admin']['user']['id']},{'$set':{'role':'admin'}})
    emp=c['accounts']['employee']['user']['id']
    r=c['accounts']['admin']['session'].patch(BASE+'/api/admin/users/'+emp,json={'role':'employee'},timeout=30)
    assert r.status_code==200
    manifest={'tag':tag,'password':password,'accounts':{k:{'email':v['email'],'id':v['user']['id']} for k,v in c['accounts'].items()},'original':c['original'],'ids':c['ids']}
    c['manifest']=manifest
    Path('/app/test_reports/test_state.json').write_text(json.dumps(manifest))
    os.chmod('/app/test_reports/test_state.json',0o600)
    yield c
    manifest['ids']=c['ids']
    Path('/app/test_reports/test_state.json').write_text(json.dumps(manifest))

def call(c, who, method, path, **kw):
    session=c['accounts'][who]['session'] if who else requests
    return getattr(session,method)(BASE+'/api'+path,timeout=180,**kw)

def png():
    buf=io.BytesIO(); Image.new('RGB',(40,40),'blue').save(buf,format='PNG'); return buf.getvalue()

def upload(c,who,purpose,context='',ext='png',content=None):
    r=call(c,who,'post','/files',data={'purpose':purpose,'context_id':context},files={'file':('TEST_file.'+ext,content if content is not None else png())})
    assert r.status_code==200,r.text
    assert isinstance(r.json()['id'],str)
    return r.json()['id']

def test_01_health_public(ctx):
    r=call(ctx,None,'get','/health'); assert r.json()=={'status':'ok','phase':1}
    r=call(ctx,None,'get','/site'); assert r.status_code==200 and 'about' in r.json()
    r=call(ctx,None,'get','/categories'); assert len(r.json())>=3

def test_02_cookie_and_permissions(ctx):
    r=call(ctx,'visitor','post','/auth/login',json={'email':ctx['accounts']['visitor']['email'],'password':ctx['password']})
    cookie=next(h for h in r.raw.headers.getlist('Set-Cookie') if h.startswith('kura_session=')); assert all(v in cookie for v in ['HttpOnly','Secure','Path=/api'])
    for who in [None,'visitor','employee']:
        for path in ['/admin/users','/admin/courses','/admin/overview','/admin/purchases','/admin/audit']:
            r=call(ctx,who,'get',path); assert r.status_code==(401 if who is None else 403) and 'detail' in r.json()

def test_03_uniqueness_and_krc_validation(ctx):
    user=ctx['accounts']['pending']['user']
    base={'name':'TEST duplicate','email':ctx['accounts']['visitor']['email'].upper(),'phone':'+19998887776','password':ctx['password']}
    r=call(ctx,None,'post','/auth/register',json=base); assert r.status_code==409 and 'detail' in r.json()
    profile={k:user.get(k) for k in ['name','phone','is_student','university','research_field','krc','registration_date']}
    profile['registration_date']=None
    r=call(ctx,'pending','put','/auth/profile',json=profile); assert r.status_code==422 and 'detail' in r.json()
    profile.update(registration_date='2025-01-01',phone='00'+ctx['accounts']['visitor']['user']['phone'][1:])
    r=call(ctx,'pending','put','/auth/profile',json=profile); assert r.status_code==409

def test_04_settings_category_course(ctx):
    settings={**ctx['original'],'currency':'USD','payment_instructions':'TEST bank transfer instructions'}
    r=call(ctx,'admin','put','/admin/settings',json=settings); assert r.status_code==200 and r.json()['currency']=='USD'
    cat=call(ctx,'admin','post','/admin/categories',json={'name':ctx['tag']}).json(); ctx['ids']['category']=cat['id']
    data={'title':ctx['tag']+' paid','description':'TEST medical research course description','category_id':cat['id'],'price':'12.34','free_for_students':True,'published':False}
    r=call(ctx,'admin','post','/admin/courses',json=data); assert r.status_code==200,r.text
    cid=r.json()['id'];ctx['ids']['course']=cid
    assert call(ctx,None,'get','/courses/'+cid).status_code==404
    data['published']=True
    r=call(ctx,'admin','put','/admin/courses/'+cid,json=data);assert r.status_code==200
    detail=call(ctx,None,'get','/courses/'+cid).json(); assert detail['price_minor']==1234 and detail['published'] and not detail['has_access']
    assert call(ctx,'admin','delete','/admin/categories/'+cat['id']).status_code==409
    ctx['course_data']=data

def test_05_real_lecture_storage(ctx):
    cid=ctx['ids']['course']
    fid=upload(ctx,'admin','lecture',cid,'txt',b'TEST private lecture content')
    ctx['ids']['lecture_file']=fid
    r=call(ctx,'admin','post','/admin/courses/'+cid+'/lectures',json={'title':'TEST lecture','file_id':fid,'order':1}); assert r.status_code==200,r.text
    lid=r.json()['id'];ctx['ids']['lecture']=lid
    r=call(ctx,'admin','put','/admin/lectures/'+lid,json={'title':'TEST edited lecture','file_id':fid,'order':2});assert r.status_code==200
    detail=call(ctx,None,'get','/courses/'+cid).json(); assert detail['lectures'][0]['title']=='TEST edited lecture' and 'file_id' not in detail['lectures'][0]
    for who in [None,'visitor','pending','employee']:
        r=call(ctx,who,'get','/files/'+fid); assert r.status_code==(401 if who is None else 403)
    r=call(ctx,'admin','get','/files/'+fid,headers={'Range':'bytes=0-3'});assert r.status_code==206 and r.content==b'TEST'

def test_06_purchase_pending_receipt(ctx):
    cid=ctx['ids']['course'];r=call(ctx,'visitor','post','/courses/'+cid+'/purchase');assert r.status_code==200,r.text
    p=r.json();ctx['ids']['purchase']=p['id'];assert p['currency']=='USD' and p['amount_minor']==1234 and p['payment_instructions']=='TEST bank transfer instructions'
    assert call(ctx,'visitor','get','/my/purchases/course/'+cid).json()['purchase']['id']==p['id']
    fid=upload(ctx,'visitor','receipt',p['id']);ctx['ids']['receipt_file']=fid
    r=call(ctx,'visitor','post','/purchases/'+p['id']+'/receipt',json={'file_id':fid});assert r.status_code==200 and r.json()['status']=='pending'
    assert not call(ctx,'visitor','get','/courses/'+cid).json()['has_access']
    for who in [None,'other','employee']:
        assert call(ctx,who,'get','/files/'+fid).status_code==(401 if who is None else 403)
    assert call(ctx,'visitor','get','/files/'+fid).content==png()

def test_07_reject_replace_approve(ctx):
    pid=ctx['ids']['purchase'];cid=ctx['ids']['course']
    r=call(ctx,'admin','post','/admin/purchases/'+pid+'/review',json={'decision':'rejected'});assert r.status_code==422
    r=call(ctx,'admin','post','/admin/purchases/'+pid+'/review',json={'decision':'rejected','reason':'TEST unreadable receipt'});assert r.status_code==200
    fid=upload(ctx,'visitor','receipt',pid)
    r=call(ctx,'visitor','post','/purchases/'+pid+'/receipt',json={'file_id':fid});assert r.status_code==200
    assert len(r.json()['receipts'])==2 and r.json()['receipts'][0]['reason']=='TEST unreadable receipt'
    assert call(ctx,'admin','post','/admin/purchases/'+pid+'/review',json={'decision':'approved'}).status_code==200
    p=call(ctx,'visitor','get','/my/purchases/course/'+cid).json()['purchase'];assert p['status']=='approved' and p['receipts'][1]['status']=='approved'
    assert call(ctx,'visitor','get','/courses/'+cid).json()['has_access']
    assert call(ctx,'visitor','get','/files/'+ctx['ids']['lecture_file']).content==b'TEST private lecture content'
    assert call(ctx,'admin','post','/admin/purchases/'+pid+'/review',json={'decision':'approved'}).status_code==409
    assert call(ctx,'visitor','post','/courses/'+cid+'/purchase').json()['id']==pid
    assert any(c['id']==cid for c in call(ctx,'visitor','get','/my/courses').json())

def test_08_student_approval_profile(ctx):
    user=ctx['accounts']['pending']['user'];cid=ctx['ids']['course']
    assert call(ctx,'pending','get','/auth/me').json()['role']=='visitor'
    r=call(ctx,'admin','patch','/admin/users/'+user['id'],json={'student_decision':'approved'});assert r.status_code==200 and r.json()['role']=='student'
    assert call(ctx,'pending','get','/courses/'+cid).json()['has_access']
    profile={k:user.get(k) for k in ['name','phone','is_student','university','research_field','krc','registration_date']};profile['krc']='KRCCHANGED'
    assert call(ctx,'pending','put','/auth/profile',json=profile).status_code==403
    profile['krc']=user['krc'];profile['name']='TEST student updated';profile['role']='admin'
    r=call(ctx,'pending','put','/auth/profile',json=profile);assert r.status_code==200 and r.json()['role']=='student'
    assert call(ctx,'pending','get','/auth/me').json()['name']=='TEST student updated'

def test_09_avatar_and_bad_uploads(ctx):
    fid=upload(ctx,'visitor','avatar');ctx['ids']['avatar']=fid
    assert call(ctx,'visitor','get','/auth/me').json()['avatar_id']==fid
    assert call(ctx,'visitor','get','/files/'+fid).content==png()
    for who in [None,'other','employee']:
        assert call(ctx,who,'get','/files/'+fid).status_code==(401 if who is None else 403)
    for filename, content, code in [('bad.png',b'not an image',422),('bad.exe',b'bad',422),('large.png',b'x'*(5*1024*1024+1),413)]:
        r=call(ctx,'visitor','post','/files',data={'purpose':'avatar'},files={'file':(filename,content)});assert r.status_code==code and 'detail' in r.json()

def test_10_block_revokes_cookie(ctx):
    uid=ctx['accounts']['visitor']['user']['id'];r=call(ctx,'admin','patch','/admin/users/'+uid,json={'status':'blocked'});assert r.status_code==200
    assert call(ctx,'visitor','get','/auth/me').status_code in (401,403)
    assert call(ctx,'visitor','get','/files/'+ctx['ids']['lecture_file']).status_code in (401,403)
    assert not call(ctx,'visitor','get','/courses/'+ctx['ids']['course']).json()['has_access']
    assert call(ctx,'admin','patch','/admin/users/'+uid,json={'status':'active'}).json()['status']=='active'
    assert call(ctx,'visitor','post','/auth/login',json={'email':ctx['accounts']['visitor']['email'],'password':ctx['password']}).status_code==200

def test_11_currency_snapshots_balances(ctx):
    settings={**ctx['original'],'currency':'EUR','payment_instructions':'TEST changed instructions'}
    assert call(ctx,'admin','put','/admin/settings',json=settings).status_code==200
    assert call(ctx,None,'get','/courses/'+ctx['ids']['course']).status_code==404
    p=call(ctx,'visitor','get','/my/purchases/course/'+ctx['ids']['course']).json()['purchase'];assert p['currency']=='USD' and p['amount_minor']==1234 and p['payment_instructions']=='TEST bank transfer instructions'
    data=call(ctx,'visitor','get','/my/purchases').json();assert data['balances']==[{'currency':'USD','paid_minor':1234,'remaining_minor':0}]
    course={**ctx['course_data'],'price':'23.45'}
    assert call(ctx,'admin','put','/admin/courses/'+ctx['ids']['course'],json=course).json()['currency']=='EUR'
    assert call(ctx,None,'get','/courses/'+ctx['ids']['course']).json()['price_minor']==2345

def test_12_reset_neutral_expired_single_use(ctx):
    r=call(ctx,None,'post','/auth/forgot-password',json={'email':'no-account-'+ctx['tag'].lower()+'@example.com'});assert r.status_code==200 and 'message' in r.json()
    uid=ctx['accounts']['other']['user']['id'];token=secrets.token_urlsafe(40)
    ctx['db'].reset_tokens.insert_one({'token_hash':digest(token),'user_id':uid,'expires_at':datetime.now(timezone.utc)-timedelta(minutes=1)})
    assert call(ctx,None,'post','/auth/reset-password',json={'token':token,'password':ctx['password']}).status_code==400
    token=secrets.token_urlsafe(40);ctx['db'].reset_tokens.insert_one({'token_hash':digest(token),'user_id':uid,'expires_at':datetime.now(timezone.utc)+timedelta(minutes=30)})
    r=call(ctx,None,'post','/auth/reset-password',json={'token':token,'password':ctx['password']});assert r.status_code==200 and 'message' in r.json()
    assert call(ctx,'other','get','/auth/me').status_code==401
    assert call(ctx,None,'post','/auth/reset-password',json={'token':token,'password':ctx['password']}).status_code==400

def test_13_real_managed_email(ctx):
    from mailer import send_reset_email
    provider_id=asyncio.run(send_reset_email({'name':'TEST KURA','email':'delivered@resend.dev'},BASE+'/reset-password#token='+secrets.token_urlsafe(40)))
    assert isinstance(provider_id,str) and provider_id
    print('Managed email provider accepted message; id present. Delivery inbox not inspected.')

def test_14_separate_owner_invite(ctx):
    uid=ctx['accounts']['employee']['user']['id'];token=secrets.token_urlsafe(40)
    ctx['db'].owner_invites.insert_one({'token_hash':digest(token),'used':False,'expires_at':datetime.now(timezone.utc)+timedelta(minutes=5),'test_tag':ctx['tag']})
    assert call(ctx,None,'post','/auth/activate-owner',json={'token':token}).status_code==401
    assert call(ctx,'employee','post','/auth/activate-owner',json={'token':token}).status_code==200
    assert call(ctx,'employee','get','/auth/me').json()['role']=='admin'
    assert call(ctx,'employee','post','/auth/activate-owner',json={'token':token}).status_code==400
    ctx['db'].users.update_one({'id':uid},{'$set':{'role':'employee'}})

def test_15_audit_filters_and_pagination(ctx):
    r=call(ctx,'admin','get','/audit',params={'q':ctx['ids']['purchase']});assert r.status_code==404
    r=call(ctx,'admin','get','/admin/audit',params={'q':ctx['ids']['purchase']});assert r.status_code==200
    actions={a['action'] for a in r.json()['items']};assert {'purchase_created','receipt_submitted','receipt_rejected','receipt_approved'}<=actions
    assert call(ctx,'admin','get','/admin/users',params={'q':ctx['tag'],'page':2}).json()['items']==[]
    assert call(ctx,None,'get','/courses',params={'q':ctx['tag']}).json()['total']==1

def test_16_pdf_storage_and_lecture_delete(ctx):
    buf=io.BytesIO();Image.new('RGB',(40,40),'white').save(buf,format='PDF');data=buf.getvalue()
    fid=upload(ctx,'admin','lecture',ctx['ids']['course'],'pdf',data)
    r=call(ctx,'admin','post','/admin/courses/'+ctx['ids']['course']+'/lectures',json={'title':'TEST PDF lecture','file_id':fid,'order':1});assert r.status_code==200
    lid=r.json()['id'];assert call(ctx,'admin','get','/files/'+fid).content==data
    assert call(ctx,'admin','delete','/admin/lectures/'+lid).json()['success']
    assert lid not in [l['id'] for l in call(ctx,'admin','get','/courses/'+ctx['ids']['course']).json()['lectures']]
    assert call(ctx,'visitor','get','/files/'+fid).status_code==403