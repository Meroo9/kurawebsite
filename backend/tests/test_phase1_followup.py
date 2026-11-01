# Follow-up probes reuse isolated Phase 1 accounts; run before cleanup.
import json, os, sys, secrets
from pathlib import Path
from datetime import datetime, timezone, timedelta
import requests, pytest
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv('/app/frontend/.env');load_dotenv('/app/backend/.env')
BASE=os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
STATE={}
DB=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]

@pytest.fixture(scope='module',autouse=True)
def require_test_state():
    path=Path('/app/test_reports/test_state.json')
    if not path.exists(): pytest.skip('Run test_phase1.py first; follow-up requires retained isolated state')
    STATE.update(json.loads(path.read_text()))

@pytest.fixture(scope='module')
def sessions():
    result={}
    for name in ['admin','visitor','employee','pending']:
        s=requests.Session();s.headers['X-Kura-Request']='1';r=s.post(BASE+'/api/auth/login',json={'email':STATE['accounts'][name]['email'],'password':STATE['password']},timeout=30)
        assert r.status_code==200,r.text
        result[name]=s
    return result

def test_cookie_external_origin(sessions):
    cookie=sessions['visitor'].cookies.get('kura_session')
    assert cookie
    r=sessions['visitor'].post(BASE+'/api/auth/login',json={'email':STATE['accounts']['visitor']['email'],'password':STATE['password']},timeout=30)
    raw=next(h for h in r.raw.headers.getlist('Set-Cookie') if h.startswith('kura_session='))
    attrs={a.strip().partition('=')[0].lower():a.strip().partition('=')[2] for a in raw.split(';')[1:]}
    assert attrs['path']=='/api' and 'secure' in attrs and 'httponly' in attrs, f'External cookie attributes: {attrs}'
    print('Understood proxy cookie rewrite:', attrs)

def test_employee_and_anonymous_denial(sessions):
    for who in [None,'visitor','employee']:
        s=sessions.get(who,requests)
        for path in ['/admin/users','/admin/courses','/admin/overview','/admin/purchases','/admin/audit']:
            r=s.get(BASE+'/api'+path,timeout=30);assert r.status_code==(401 if who is None else 403) and 'detail' in r.json()

def test_duplicate_normalized_krc(sessions):
    u=DB.users.find_one({'id':STATE['accounts']['pending']['id']})
    data={'name':'TEST duplicate KRC','email':STATE['tag'].lower()+'dup@example.com','phone':'+19992224444','password':STATE['password'],'krc':' '+u['krc'].lower()+' ','university':'TEST university','research_field':'TEST field','registration_date':'2025-01-01'}
    r=requests.post(BASE+'/api/auth/register',json=data,timeout=30);assert r.status_code==409 and 'detail' in r.json()

def test_employee_creation_edit_and_expired_invite(sessions):
    data={'name':STATE['tag']+' UI employee','email':STATE['tag'].lower()+'createdemp@example.com','phone':'+19993334444','password':STATE['password']}
    r=sessions['admin'].post(BASE+'/api/admin/employees',json=data,timeout=30);assert r.status_code==200,r.text
    uid=r.json()['id'];assert r.json()['role']=='employee'
    r=sessions['admin'].patch(BASE+'/api/admin/users/'+uid,json={'name':STATE['tag']+' edited employee'},timeout=30);assert r.json()['name'].endswith('edited employee')
    r=sessions['admin'].get(BASE+'/api/admin/users',params={'q':data['email']},timeout=30);assert r.json()['items'][0]['name'].endswith('edited employee')
    token=secrets.token_urlsafe(40)
    from core import digest
    DB.owner_invites.insert_one({'token_hash':digest(token),'used':False,'expires_at':datetime.now(timezone.utc)-timedelta(minutes=1),'test_tag':STATE['tag']})
    assert sessions['visitor'].post(BASE+'/api/auth/activate-owner',json={'token':token},timeout=30).status_code==400

def test_multicurrency_and_receipt_oversize(sessions):
    cid=STATE['ids']['course'];s=sessions['admin']
    r=sessions['employee'].post(BASE+'/api/courses/'+cid+'/purchase',timeout=30);assert r.status_code==403
    r=sessions['visitor'].post(BASE+'/api/courses/'+cid+'/purchase',timeout=30);assert r.json()['currency']=='USD'
    r=sessions['pending'].get(BASE+'/api/my/courses',timeout=30);assert any(c['id']==cid for c in r.json())
    # Second paid course ensures historical balances stay separate by currency.
    course={'title':STATE['tag']+' second EUR','description':'TEST second currency course description','category_id':STATE['ids']['category'],'price':'5.67','published':True}
    r=s.post(BASE+'/api/admin/courses',json=course,timeout=30);assert r.status_code==200
    cid2=r.json()['id'];r=sessions['visitor'].post(BASE+'/api/courses/'+cid2+'/purchase',timeout=30);assert r.status_code==200 and r.json()['currency']=='EUR'
    pid=r.json()['id'];STATE['ids']['second_course']=cid2;STATE['ids']['second_purchase']=pid
    Path('/app/test_reports/test_state.json').write_text(json.dumps(STATE))
    r=sessions['visitor'].post(BASE+'/api/files',data={'purpose':'receipt','context_id':pid},files={'file':('large.pdf',b'%PDF-'+b'x'*(10*1024*1024))},timeout=60);assert r.status_code==413
    r=sessions['visitor'].post(BASE+'/api/files',data={'purpose':'receipt','context_id':pid},files={'file':('invalid.pdf',b'invalid')},timeout=60);assert r.status_code==422
    balances=sessions['visitor'].get(BASE+'/api/my/purchases',timeout=30).json()['balances'];assert {b['currency'] for b in balances}=={'USD','EUR'}

sys.path.insert(0,'/app/backend')