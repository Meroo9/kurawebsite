# Boundary pagination and permission checks using retained isolated fixture state.
import json,os
from pathlib import Path
import requests,pytest
from pymongo import MongoClient
from test_research_posts import BASE,STATE,ok,denied,create,quoted,upload,call

@pytest.fixture(scope='module')
def x():
    if not STATE.exists():pytest.skip('Run isolated research/posts setup first')
    c=json.loads(STATE.read_text());c['db']=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    for who,account in c['accounts'].items():
        s=requests.Session();s.headers.update({'X-Kura-Request':'1','Origin':BASE});r=s.post(BASE+'/api/auth/login',json={'email':account['email'],'password':c['password']},timeout=60);assert r.status_code==200,r.text;account['session']=s
    return c

def test_01_image_removal_ui_persistence_diagnostic(x):
    row=x['db'].posts.find_one({'title':x['tag']+' UI عنوان معدل'},{'_id':0})
    assert row is not None
    print('UI edited post:',{k:row[k] for k in ('id','title','image_id','published')})
    assert row['image_id'] is None, 'UI remove-image saved a non-null image ID'

def test_02_research_pagination_status_and_actor_denial(x):
    existing=x['db'].research_requests.count_documents({'owner_id':x['accounts']['student']['id']})
    for i in range(max(0,13-existing)):create(x,'student','page'+str(i))
    one=ok(x,'student','get','/research');two=ok(x,'student','get','/research?page=2')
    assert len(one['items'])==12 and len(two['items'])==one['total']-12 and not {r['id'] for r in one['items']}&{r['id'] for r in two['items']}
    draft=next(r for r in one['items'] if r['status']=='draft');rid=draft['id']
    assert all(r['status']=='draft' for r in ok(x,'student','get','/research?status=draft')['items'])
    denied(x,'employee1','post',f'/research/{rid}/action',403,{'action':'cancel','note':'TEST forbidden'})
    denied(x,'visitor','post',f'/research/{rid}/submit',403)
    denied(x,'student','post',f'/research/{rid}/action',403,{'action':'start'})
    denied(x,'student','post',f'/research/{rid}/action',403,{'action':'approve_cancel','note':'TEST forbidden'})

def test_03_posts_and_comments_page_boundaries(x):
    pids=[]
    for i in range(7):pids.append(ok(x,'admin','post','/admin/posts',{'title':x['tag']+' pagination '+str(i),'body':'TEST valid scientific article content','published':True})['id'])
    path='/posts?q='+x['tag']+' pagination';one=ok(x,None,'get',path);two=ok(x,None,'get',path+'&page=2')
    assert len(one['items'])==6 and len(two['items'])==1 and one['total']==7
    pid=pids[0]
    for i in range(16):ok(x,'student','post',f'/posts/{pid}/comments',{'body':'TEST comment '+str(i)})
    one=ok(x,None,'get',f'/posts/{pid}/comments');two=ok(x,None,'get',f'/posts/{pid}/comments?page=2')
    assert len(one['items'])==15 and len(two['items'])==1 and one['total']==16 and not {r['id'] for r in one['items']}&{r['id'] for r in two['items']}
    for pid in pids:ok(x,'admin','delete','/admin/posts/'+pid)

def test_04_return_preserves_current_round_results(x):
    rid=create(x,'visitor','return_probe');quoted(x,rid,'visitor')
    ok(x,'employee1','post',f'/research/{rid}/action',{'action':'claim'})
    old=upload(x,'employee1','research_result',rid)
    ok(x,'employee1','post',f'/research/{rid}/action',{'action':'return','note':'TEST invalid result returned'})
    ok(x,'employee2','post',f'/research/{rid}/action',{'action':'claim'})
    r=call(x,'employee2','post',f'/research/{rid}/action',json={'action':'deliver'})
    print('New assignee deliver without upload:',r.status_code,r.json().get('status'))
    assert r.status_code==200 and r.json()['status']=='ready_payment'
    assert old in r.json()['released_file_ids']  # Specification permits any uploaded current-round file, not only new uploader.

def test_05_cancellation_settlement_financial_notes_hidden_from_employee(x):
    rid=x['ids']['return_probe']
    ok(x,'visitor','post',f'/research/{rid}/action',{'action':'cancel','note':'TEST cancel after assignment'})
    note='TEST private financial settlement: quote 100 USD, paid 0 USD, remaining 100 USD'
    ok(x,'admin','post',f'/research/{rid}/action',{'action':'reject_cancel','note':note})
    employee=ok(x,'employee2','get',f'/research/{rid}')
    assert note not in json.dumps(employee), 'Admin cancellation settlement note leaks through non-financial employee event history'