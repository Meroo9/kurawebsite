# Remove only this run's isolated fixtures; preserve real users, settings, courses and owner invite.
import os,json
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv('/app/backend/.env')
state_path=Path('/app/test_reports/research_test_state.json')
state=json.loads(state_path.read_text())
db=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
uids=[a['id'] for a in state['accounts'].values()]
assert all(db.users.find_one({'id':uid,'name':{'$regex':'^'+state['tag']}}) for uid in uids)
research_ids=[r['id'] for r in db.research_requests.find({'owner_id':{'$in':uids}},{'_id':0,'id':1})]
post_ids=[r['id'] for r in db.posts.find({'author_id':{'$in':uids}},{'_id':0,'id':1})]
file_ids=[r['id'] for r in db.files.find({'owner_id':{'$in':uids}},{'_id':0,'id':1})]
course_ids=[r['id'] for r in db.courses.find({'title':{'$regex':'^'+state['tag']}},{'_id':0,'id':1})]
deleted={}
for collection,query in [
    ('post_comments',{'$or':[{'post_id':{'$in':post_ids}},{'user_id':{'$in':uids}}]}),
    ('post_reactions',{'$or':[{'post_id':{'$in':post_ids}},{'user_id':{'$in':uids}}]}),
    ('posts',{'id':{'$in':post_ids}}),('research_requests',{'id':{'$in':research_ids}}),
    ('lectures',{'course_id':{'$in':course_ids}}),('courses',{'id':{'$in':course_ids}}),
    ('purchases',{'user_id':{'$in':uids}}),('files',{'id':{'$in':file_ids}}),
    ('sessions',{'user_id':{'$in':uids}}),('reset_tokens',{'user_id':{'$in':uids}}),
    ('audit',{'$or':[{'user_id':{'$in':uids}},{'target':{'$in':research_ids+post_ids+file_ids+course_ids}}]}),
    ('users',{'id':{'$in':uids}})
]:deleted[collection]=db[collection].delete_many(query).deleted_count
db.settings.replace_one({'id':'site'},state['original'])
for row in state['course_states']:db.courses.update_one({'id':row['id']},{'$set':{'published':row['published']}})
checks={
    'settings_restored':db.settings.find_one({'id':'site'},{'_id':0})==state['original'],
    'original_courses_preserved':all(db.courses.find_one({'id':r['id'],'published':r['published']}) is not None for r in state['course_states']),
    'test_users_removed':db.users.count_documents({'id':{'$in':uids}})==0,
    'test_files_removed':db.files.count_documents({'id':{'$in':file_ids}})==0,
    'test_requests_removed':db.research_requests.count_documents({'id':{'$in':research_ids}})==0,
    'test_posts_removed':db.posts.count_documents({'id':{'$in':post_ids}})==0
}
assert all(checks.values()),checks
state_path.unlink()
result={'deleted':deleted,'checks':checks,'managed_object_deletion':'Provider has no delete API; test metadata removed to revoke access. No real owner invitation touched.'}
Path('/app/test_reports/research_cleanup_results.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result,indent=2))