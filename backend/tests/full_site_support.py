# Isolated full-site fixtures and public-origin API helpers; no real account/invitation mutation.
import os, json, secrets, hashlib, io
from pathlib import Path
from datetime import datetime, timezone
import bcrypt, requests
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import json_util
from PIL import Image

load_dotenv('/app/frontend/.env'); load_dotenv('/app/backend/.env')
BASE=os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
ROOT=Path('/app/test_reports/full_site_roles'); ROOT.mkdir(parents=True,exist_ok=True)
STATE=ROOT/'private_state.json'

def save(c):
    d={k:v for k,v in c.items() if k not in ('db','sessions','accounts')}
    d['accounts']={k:{a:b for a,b in v.items() if a!='session'} for k,v in c['accounts'].items()}
    d['cookies']={k:v['session'].cookies.get_dict() for k,v in c['accounts'].items()}
    STATE.write_text(json.dumps(d)); STATE.chmod(0o600)

def load():
    c=json.loads(STATE.read_text()); c['db']=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    for role,a in c['accounts'].items():
        s=requests.Session(); s.headers.update({'X-Kura-Request':'1','Origin':BASE});s.cookies.update(c['cookies'].get(role,{}));a['session']=s
    return c

def req(c,role,method,path,**kw):
    return (c['accounts'][role]['session'] if role else requests).request(method,BASE+'/api'+path,timeout=180,**kw)

def ok(c,role,method,path,data=None):
    r=req(c,role,method,path,**({'json':data} if data is not None else {}));assert r.status_code==200,(path,r.status_code,r.text);return r.json()

def denied(c,role,method,path,code,data=None):
    r=req(c,role,method,path,**({'json':data} if data is not None else {}));assert r.status_code==code,(path,r.status_code,r.text);assert 'detail' in r.json()

def png():
    b=io.BytesIO();Image.new('RGB',(80,60),'#155bea').save(b,'PNG');return b.getvalue()

def upload(c,role,purpose,context='',ext='txt',body=None):
    r=req(c,role,'post','/files',data={'purpose':purpose,'context_id':context},files={'file':('TEST_'+('اسمملفطويل'*14)+'.'+ext,body if body is not None else (png() if ext=='png' else b'TEST private lecture content'))})
    assert r.status_code==200,r.text;save(c);return r.json()['id']

def setup():
    assert not STATE.exists(),'Unclean prior run; clean it before creating more fixtures'
    db=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    c={'db':db,'tag':'TEST_FULL_'+secrets.token_hex(5),'password':secrets.token_urlsafe(22),'accounts':{},'ids':{},'course_ids':[],'category_ids':[],'post_ids':[],
       'original':db.settings.find_one({'id':'site'},{'_id':0}),
       'original_invites':json_util.dumps(list(db.owner_invites.find({})),sort_keys=True),
       'original_courses':json_util.dumps(list(db.courses.find({})),sort_keys=True)}
    save(c)
    for role in ['admin','visitor','pending','student','employee1','employee2','other','blocked','inactive']:
        payload={'name':c['tag']+' '+role,'email':c['tag'].lower()+role+'@example.com','phone':'+1999'+str(secrets.randbelow(90000000)+10000000),'password':c['password']}
        if role in ('pending','student'):payload.update(is_student=True,krc='KRC'+secrets.token_hex(7).upper(),university='TEST university',research_field='TEST medicine',registration_date='2025-01-01')
        s=requests.Session();s.headers.update({'X-Kura-Request':'1','Origin':BASE})
        if role in ('visitor','pending','student','other'):
            r=s.post(BASE+'/api/auth/register',json={**payload,'role':'admin'},timeout=60);assert r.status_code==200,r.text;row=r.json();assert row['role']=='visitor'
        else:
            row={k:v for k,v in payload.items() if k!='password'}
            row.update(id=secrets.token_hex(12),role='employee' if role.startswith('employee') else ('admin' if role=='admin' else 'visitor'),status='active',is_student=False,student_status='none',krc=None,registration_date=None,university='',research_field='',avatar_id=None,created_at=datetime.now(timezone.utc).isoformat())
            db.users.insert_one({**row,'password_hash':bcrypt.hashpw(hashlib.sha256(c['password'].encode()).digest(),bcrypt.gensalt()).decode()})
        c['accounts'][role]={'id':row['id'],'email':payload['email'],'name':payload['name'],'phone':payload['phone'],'session':s};save(c)
        if role not in ('visitor','pending','student','other'):assert ok(c,role,'post','/auth/login',{'email':payload['email'],'password':c['password']})['id']==row['id']
    ok(c,'admin','patch','/admin/users/'+c['accounts']['student']['id'],{'student_decision':'approved'})
    for role in ('blocked','inactive'):ok(c,'admin','patch','/admin/users/'+c['accounts'][role]['id'],{'status':role})
    # Fill only missing settings directly: API currency changes unpublish real courses.
    edits={}
    if not c['original']['currency']:edits['currency']='USD'
    if not c['original']['payment_instructions'].strip():edits['payment_instructions']='TEST external transfer instructions'
    if edits:db.settings.update_one({'id':'site'},{'$set':edits})
    c['currency']=db.settings.find_one({'id':'site'})['currency'];save(c);return c

def cleanup():
    c=load();db=c['db'];uids=[a['id'] for a in c['accounts'].values()]
    assert all(db.users.find_one({'id':u,'name':{'$regex':'^'+c['tag']}}) for u in uids)
    rids=[r['id'] for r in db.research_requests.find({'owner_id':{'$in':uids}})]
    pids=[r['id'] for r in db.posts.find({'author_id':{'$in':uids}})]
    fids=[r['id'] for r in db.files.find({'owner_id':{'$in':uids}})]
    cids=c['course_ids'];cats=c['category_ids']
    lids=[r['id'] for r in db.lectures.find({'course_id':{'$in':cids}})]
    comments=[r['id'] for r in db.post_comments.find({'user_id':{'$in':uids}})]
    purchases=[r['id'] for r in db.purchases.find({'user_id':{'$in':uids}})]
    targets=rids+pids+fids+cids+cats+lids+comments+purchases+uids
    counts={}
    for collection,query in [('post_comments',{'$or':[{'post_id':{'$in':pids}},{'user_id':{'$in':uids}}]}),('post_reactions',{'$or':[{'post_id':{'$in':pids}},{'user_id':{'$in':uids}}]}),('posts',{'id':{'$in':pids}}),('research_requests',{'id':{'$in':rids}}),('lectures',{'id':{'$in':lids}}),('courses',{'id':{'$in':cids}}),('categories',{'id':{'$in':cats}}),('purchases',{'id':{'$in':purchases}}),('files',{'id':{'$in':fids}}),('sessions',{'user_id':{'$in':uids}}),('reset_tokens',{'user_id':{'$in':uids}}),('audit',{'$or':[{'user_id':{'$in':uids}},{'target':{'$in':targets}}]}),('users',{'id':{'$in':uids}})]:
        counts[collection]=db[collection].delete_many(query).deleted_count
    db.settings.replace_one({'id':'site'},c['original'])
    checks={'settings_exact':db.settings.find_one({'id':'site'},{'_id':0})==c['original'],'courses_exact':json_util.dumps(list(db.courses.find({})),sort_keys=True)==c['original_courses'],'owner_invites_exact':json_util.dumps(list(db.owner_invites.find({})),sort_keys=True)==c['original_invites'],'users_removed':db.users.count_documents({'id':{'$in':uids}})==0,'files_removed':db.files.count_documents({'id':{'$in':fids}})==0}
    (ROOT/'cleanup.json').write_text(json.dumps({'deleted':counts,'checks':checks,'storage':'Metadata revoked; provider has no physical object delete API','shared_rate_limits':'Preserved; TTL expiry only'},indent=2));assert all(checks.values()),checks
    STATE.unlink();print('Cleanup verified',checks)

if __name__=='__main__':
    import sys
    cleanup() if '--cleanup' in sys.argv else setup()