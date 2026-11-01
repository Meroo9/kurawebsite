# Explicit cleanup after API and browser checks. Leaves existing owner invites untouched.
import os,json,requests
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
load_dotenv('/app/frontend/.env');load_dotenv('/app/backend/.env')
BASE=os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
state=json.loads(Path('/app/test_reports/test_state.json').read_text())
db=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
tag=state['tag']
uids=[u['id'] for u in db.users.find({'$or':[{'id':{'$in':[u['id'] for u in state['accounts'].values()]}},{'name':{'$regex':'^'+tag}}]})]
cids=[c['id'] for c in db.courses.find({'title':{'$regex':'^'+tag}})]
fids=[f['id'] for f in db.files.find({'owner_id':{'$in':uids}})]
s=requests.Session()
s.headers['X-Kura-Request']='1'
r=s.post(BASE+'/api/auth/login',json={'email':state['accounts']['admin']['email'],'password':state['password']},timeout=30)
if r.status_code==200:
    for cid in cids:
        r=s.delete(BASE+'/api/admin/courses/'+cid,timeout=30)
        assert r.status_code==200 and r.json()['success']
        assert requests.get(BASE+'/api/courses/'+cid,timeout=30).status_code==404
    print('PASS course archive hides course metadata')
    r=s.put(BASE+'/api/admin/settings',json=state['original'],timeout=30)
    assert r.status_code==200
else:
    print('Admin login unavailable during cleanup; restoring settings directly')
    db.settings.replace_one({'id':'site'},state['original'])
counts={}
for collection,query in [
    ('sessions',{'user_id':{'$in':uids}}),('reset_tokens',{'user_id':{'$in':uids}}),
    ('owner_invites',{'test_tag':tag}),('lectures',{'course_id':{'$in':cids}}),
    ('purchases',{'user_id':{'$in':uids}}),('files',{'owner_id':{'$in':uids}}),
    ('courses',{'id':{'$in':cids}}),('categories',{'name':{'$regex':'^'+tag}}),
    ('audit',{'$or':[{'user_id':{'$in':uids}},{'target':{'$in':fids+cids}}]}),
    ('users',{'id':{'$in':uids}})]:
    counts[collection]=db[collection].delete_many(query).deleted_count
assert db.settings.find_one({'id':'site'},{'_id':0})==state['original']
for collection,query in [('users',{'id':{'$in':uids}}),('courses',{'id':{'$in':cids}}),('files',{'owner_id':{'$in':uids}}),('sessions',{'user_id':{'$in':uids}})]:
    assert db[collection].count_documents(query)==0
assert all(requests.get(BASE+'/api/files/'+fid,timeout=30).status_code==401 for fid in fids[:2])
Path('/app/test_reports/cleanup_results.json').write_text(json.dumps({'deleted_counts':counts,'settings_restored':True,'test_records_removed':True,'managed_storage_objects':'No provider delete API; metadata removed and access blocked','rate_limits':'Shared IP buckets left intact; expire automatically'},indent=2))
Path('/app/test_reports/test_state.json').unlink()
print('PASS cleanup and original settings verified',counts)