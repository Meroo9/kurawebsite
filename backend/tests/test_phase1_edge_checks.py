# Existing isolated test-state edge checks; execute after browser purchase flow, before cleanup.
import os,json,secrets
from pathlib import Path
from datetime import datetime,timezone,timedelta
import pytest,requests
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv('/app/frontend/.env');load_dotenv('/app/backend/.env')
BASE=os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
STATE={}
DB=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]

@pytest.fixture(scope='module',autouse=True)
def require_test_state():
    path=Path('/app/test_reports/test_state.json')
    if not path.exists(): pytest.skip('Run core and browser tests first; edge checks require retained isolated state')
    STATE.update(json.loads(path.read_text()))

@pytest.fixture(scope='module')
def sessions():
    result={}
    for name in ['admin','other']:
        s=requests.Session();s.headers['X-Kura-Request']='1';r=s.post(BASE+'/api/auth/login',json={'email':STATE['accounts'][name]['email'],'password':STATE['password']},timeout=30)
        assert r.status_code==200,r.text
        result[name]=s
    return result

def test_pagination_hides_exact_purchase_from_first_page(sessions):
    cid=STATE['ids']['course'];s=sessions['other']
    r=s.post(BASE+'/api/courses/'+cid+'/purchase',timeout=30);assert r.status_code==200
    p=r.json();STATE['ids']['other_purchase']=p['id']
    # Synthetic TEST history only, simulating a member with sixteen later purchases.
    for i in range(16):
        DB.purchases.insert_one({**p,'id':secrets.token_hex(12),'course_id':'TEST_HISTORY_'+STATE['tag']+str(i),'course_title':'TEST pagination history','created_at':(datetime.now(timezone.utc)+timedelta(seconds=i+1)).isoformat()})
    first=s.get(BASE+'/api/my/purchases',timeout=30).json()
    assert first['total']==17 and len(first['items'])==15
    assert p['id'] not in [v['id'] for v in first['items']]
    exact=s.get(BASE+'/api/my/purchases/course/'+cid,timeout=30).json()['purchase'];assert exact['id']==p['id'] and exact['status']=='awaiting_receipt'
    Path('/app/test_reports/test_state.json').write_text(json.dumps(STATE))

def test_reject_malformed_signature_only_pdf(sessions):
    pid=STATE['ids']['other_purchase']
    r=sessions['other'].post(BASE+'/api/files',data={'purpose':'receipt','context_id':pid},files={'file':('TEST_invalid.pdf',b'%PDF- totally invalid, not a PDF document')},timeout=60)
    assert r.status_code==422, f'Malformed PDF accepted: {r.status_code}'

def test_category_mutations_are_audited(sessions):
    s=sessions['admin'];r=s.post(BASE+'/api/admin/categories',json={'name':STATE['tag']+' audit category'},timeout=30);assert r.status_code==200
    cid=r.json()['id']
    r=s.put(BASE+'/api/admin/categories/'+cid,json={'name':STATE['tag']+' audit renamed'},timeout=30);assert r.status_code==200
    assert any(c['name'].endswith('audit renamed') for c in s.get(BASE+'/api/categories',timeout=30).json() if c['id']==cid)
    assert s.delete(BASE+'/api/admin/categories/'+cid,timeout=30).status_code==200
    assert cid not in [c['id'] for c in s.get(BASE+'/api/categories',timeout=30).json()]
    logs=s.get(BASE+'/api/admin/audit',params={'q':cid},timeout=30).json()
    assert logs['total']>=3, 'Category create/edit/delete emit no audit events'

def test_missing_category_update_returns_not_found(sessions):
    r=sessions['admin'].put(BASE+'/api/admin/categories/TEST_NONEXISTENT',json={'name':'TEST name'},timeout=30)
    assert r.status_code==404, f'Nonexistent category update returns {r.status_code}'
    r=sessions['admin'].delete(BASE+'/api/admin/categories/TEST_NONEXISTENT',timeout=30)
    assert r.status_code==404 and 'detail' in r.json()