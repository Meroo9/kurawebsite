# Post-security regression: CSRF/CORS, metadata/ranges, KRC and paginated member library.
import os,json,secrets
from pathlib import Path
import requests,pytest
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv('/app/frontend/.env');load_dotenv('/app/backend/.env')
BASE=os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
DB=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
STATE={}

@pytest.fixture(scope='module',autouse=True)
def require_test_state():
    path=Path('/app/test_reports/test_state.json')
    if not path.exists(): pytest.skip('Run core, follow-up and edge suites before security checks')
    STATE.update(json.loads(path.read_text()))

@pytest.fixture(scope='module')
def sessions():
    out={}
    for who in ['admin','visitor','other','pending','employee']:
        s=requests.Session();s.headers['X-Kura-Request']='1'
        r=s.post(BASE+'/api/auth/login',json={'email':STATE['accounts'][who]['email'],'password':STATE['password']},timeout=30)
        assert r.status_code==200,r.text
        out[who]=s
    return out

def test_authenticated_mutation_csrf(sessions):
    s=sessions['visitor'];s.headers.pop('X-Kura-Request')
    payload={'email':STATE['accounts']['visitor']['email'],'password':STATE['password']}
    r=s.post(BASE+'/api/auth/login',json=payload,timeout=30)
    assert r.status_code==403 and 'detail' in r.json()
    s.headers['X-Kura-Request']='1'
    r=s.post(BASE+'/api/auth/login',json=payload,headers={'Origin':'https://hostile.example'},timeout=30)
    assert r.status_code==403 and 'detail' in r.json()
    r=s.post(BASE+'/api/auth/login',json=payload,headers={'Origin':BASE},timeout=30)
    assert r.status_code==200 and r.json()['id']==STATE['accounts']['visitor']['id']
    r=requests.post(BASE+'/api/auth/login',json=payload,timeout=30)
    assert r.status_code==200 and r.json()['role']=='visitor'

def test_hostile_preflight_denied():
    headers={'Origin':'https://hostile.example','Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'X-Kura-Request,Content-Type'}
    r=requests.options(BASE+'/api/auth/profile',headers=headers,timeout=30)
    assert r.status_code==400 and 'access-control-allow-origin' not in r.headers
    headers['Origin']=BASE
    r=requests.options(BASE+'/api/auth/profile',headers=headers,timeout=30)
    assert r.status_code==200 and r.headers['access-control-allow-origin']==BASE

def test_metadata_permissions(sessions):
    for fid in [STATE['ids']['lecture_file'],STATE['ids']['receipt_file'],STATE['ids']['avatar']]:
        r=requests.get(BASE+'/api/files/'+fid+'/metadata',timeout=30)
        assert r.status_code==401 and 'detail' in r.json()
        for who in ['other','employee']:
            r=sessions[who].get(BASE+'/api/files/'+fid+'/metadata',timeout=30)
            assert r.status_code==403 and 'detail' in r.json()
        r=sessions['visitor'].get(BASE+'/api/files/'+fid+'/metadata',timeout=30)
        assert r.status_code==200 and r.json()['id']==fid and isinstance(r.json()['size'],int)
        assert 'storage_path' not in r.json() and 'owner_id' not in r.json()

def test_ranges(sessions):
    url=BASE+'/api/files/'+STATE['ids']['lecture_file'];s=sessions['visitor'];data=b'TEST private lecture content'
    for value,expected in [('bytes=0-3',b'TEST'),('bytes=-7',b'content'),('bytes=5-',data[5:])]:
        r=s.get(url,headers={'Range':value},timeout=60)
        assert r.status_code==206 and r.content==expected and int(r.headers['Content-Length'])==len(expected)
    for value in ['bytes=999-','bytes=8-2','bytes=','bytes=-0','bytes=0-1,4-5']:
        r=s.get(url,headers={'Range':value},timeout=60)
        assert r.status_code==416 and r.headers['Content-Range']=='bytes */'+str(len(data))

def test_krc_uniqueness(sessions):
    uid=STATE['accounts']['pending']['id'];s=sessions['admin']
    original=DB.users.find_one({'id':uid})['krc']
    corrected='KRC'+secrets.token_hex(8).upper()
    r=s.patch(BASE+'/api/admin/users/'+uid,json={'krc':corrected},timeout=30)
    assert r.status_code==200 and r.json()['krc']==corrected
    assert sessions['pending'].get(BASE+'/api/auth/me',timeout=30).json()['krc']==corrected
    r=s.patch(BASE+'/api/admin/users/'+STATE['accounts']['visitor']['id'],json={'krc':corrected},timeout=30)
    assert r.status_code==409 and 'detail' in r.json()
    s.patch(BASE+'/api/admin/users/'+uid,json={'krc':original},timeout=30).raise_for_status()

def test_large_library_and_filters(sessions):
    s=sessions['admin'];created=[]
    for i in range(14):
        payload={'title':STATE['tag']+' Library '+str(i),'description':'TEST searchable accessible course','category_id':STATE['ids']['category'],'price':'0','published':True}
        r=s.post(BASE+'/api/admin/courses',json=payload,timeout=30)
        assert r.status_code==200 and r.json()['title']==payload['title'];created.append(r.json()['id'])
    # Retained until browser checks; cleanup matches TEST tag.
    v=sessions['visitor']
    first=v.get(BASE+'/api/my/library',timeout=30).json()
    assert first['total']>=15 and len(first['items'])==12 and first['page']==1
    second=v.get(BASE+'/api/my/library',params={'page':2},timeout=30).json()
    assert second['page']==2 and len(second['items'])>=3
    assert not {x['id'] for x in first['items']} & {x['id'] for x in second['items']}
    filtered=v.get(BASE+'/api/my/library',params={'q':STATE['tag']+' Library','category':STATE['ids']['category']},timeout=30).json()
    assert filtered['total']==14 and len(filtered['items'])==12
    assert v.get(BASE+'/api/my/library',params={'category':'TEST_MISSING'},timeout=30).json()['total']==0
    compact=v.get(BASE+'/api/my/courses',timeout=30).json()
    assert isinstance(compact,list) and len(compact)==3

def test_public_existing_account_forgot(sessions):
    uid=STATE['accounts']['other']['id'];original=STATE['accounts']['other']['email']
    assert not DB.users.find_one({'email':'delivered@resend.dev'}), 'Assigned test mailbox already occupied'
    DB.users.update_one({'id':uid},{'$set':{'email':'delivered@resend.dev'}})
    try:
        r=requests.post(BASE+'/api/auth/forgot-password',json={'email':'delivered@resend.dev'},timeout=60)
        assert r.status_code==200 and 'message' in r.json()
        assert DB.reset_tokens.count_documents({'user_id':uid})==1, 'Managed mail failure removes reset token'
    finally:
        DB.users.update_one({'id':uid},{'$set':{'email':original}})