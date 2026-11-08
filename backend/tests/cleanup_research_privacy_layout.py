# Delete only targeted privacy/layout fixtures and verify original settings/courses/invitation unchanged.
import os, json
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import json_util

load_dotenv('/app/backend/.env')
path=Path('/app/test_reports/privacy_layout_state.json')
state=json.loads(path.read_text())
db=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
uids=[a['id'] for a in state['accounts'].values()]
assert all(db.users.find_one({'id':u,'name':{'$regex':'^'+state['tag']}}) for u in uids)
rids=[r['id'] for r in db.research_requests.find({'owner_id':{'$in':uids}})]
assert set(rids)==set(state['request_ids'])
fids=[r['id'] for r in db.files.find({'owner_id':{'$in':uids}})]
deleted={}
for col,query in [('research_requests',{'id':{'$in':rids}}),('files',{'id':{'$in':fids}}),('sessions',{'user_id':{'$in':uids}}),
                  ('audit',{'$or':[{'user_id':{'$in':uids}},{'target':{'$in':rids+fids}}]}),('users',{'id':{'$in':uids}})]:
    deleted[col]=db[col].delete_many(query).deleted_count
original=state['original_settings']
if db.settings.find_one({'id':'site'},{'_id':0})!=original:
    # This suite only fills empty currency/payment instructions; no unrelated settings modifications.
    db.settings.update_one({'id':'site'},{'$set':{'currency':original['currency'],'payment_instructions':original['payment_instructions']}})
checks={
    'settings_exactly_preserved':db.settings.find_one({'id':'site'},{'_id':0})==original,
    'courses_exactly_preserved':json_util.dumps(list(db.courses.find({})),sort_keys=True)==state['original_courses'],
    'owner_invites_exactly_preserved':json_util.dumps(list(db.owner_invites.find({})),sort_keys=True)==state['original_invites'],
    'isolated_users_removed':db.users.count_documents({'id':{'$in':uids}})==0,
    'isolated_sessions_removed':db.sessions.count_documents({'user_id':{'$in':uids}})==0,
    'isolated_requests_removed':db.research_requests.count_documents({'id':{'$in':rids}})==0,
    'isolated_file_metadata_removed':db.files.count_documents({'id':{'$in':fids}})==0}
assert all(checks.values()),checks
path.unlink();checks['private_manifest_removed']=not path.exists()
result={'deleted':deleted,'checks':checks,'storage':'Real managed storage used. Provider objects cannot be physically deleted; isolated metadata removal revokes access. No invitation or email sent.'}
Path('/app/test_reports/privacy_layout_cleanup_results.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))