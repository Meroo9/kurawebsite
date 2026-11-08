# Targeted regression fixtures; exact-ID cleanup, no real settings or invitation mutation.
import os,json,secrets,hashlib,bcrypt,requests,subprocess,io
from pathlib import Path
from datetime import datetime,timezone
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import json_util
from PIL import Image
load_dotenv('/app/frontend/.env');load_dotenv('/app/backend/.env')
BASE=os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
ROOT=Path('/app/test_reports/full_site_roles/fixes');ROOT.mkdir(parents=True,exist_ok=True)
STATE=ROOT/'private_state.json'
def save(c):
    STATE.write_text(json.dumps({k:v for k,v in c.items() if k!='db'}));STATE.chmod(0o600)
def load():
    c=json.loads(STATE.read_text());c['db']=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']];return c
def req(c,role,method,path,**kw):
    s=requests.Session();s.headers.update({'X-Kura-Request':'1','Origin':BASE})
    if role:s.cookies.update(c['cookies'].get(role,{}))
    return s.request(method,BASE+'/api'+path,timeout=180,**kw)
def ok(c,role,method,path,data=None):
    r=req(c,role,method,path,**({'json':data} if data is not None else {}));assert r.status_code==200,(path,r.status_code,r.text);return r.json()
def png():
    b=io.BytesIO();Image.new('RGB',(80,60),'#155bea').save(b,'PNG');return b.getvalue()
def upload(c,role,purpose,context,filename,body):
    r=req(c,role,'post','/files',data={'purpose':purpose,'context_id':context},files={'file':(filename,body)});assert r.status_code==200,r.text;return r.json()
def course(c,label,title=None,flag=False):
    p={'title':title or c['tag']+' '+label,'description':'TEST isolated medical education course with full visible description','category_id':c['ids']['category'],'price':'12.34','free_for_students':flag,'published':True}
    r=ok(c,'admin','post','/admin/courses',p);c['course_ids'].append(r['id']);c['ids'][label]=r['id'];save(c);return r
def setup():
    assert not STATE.exists(),'Prior fixture state requires cleanup'
    db=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    c={'db':db,'tag':'TEST_FIX_'+secrets.token_hex(4),'password':secrets.token_urlsafe(24),'accounts':{},'cookies':{},'ids':{},'course_ids':[],'category_ids':[]}
    c['original']={k:json_util.dumps(list(db[k].find({})),sort_keys=True) for k in ['settings','courses','owner_invites']};save(c)
    for role in ['admin','visitor','student','blocked','inactive']:
        row={'id':secrets.token_hex(12),'name':c['tag']+' '+role,'email':c['tag'].lower()+role+'@example.com','phone':'+1888'+str(secrets.randbelow(90000000)+10000000),'role':role if role in ('admin','student') else 'visitor','status':role if role in ('blocked','inactive') else 'active','is_student':role=='student','student_status':'approved' if role=='student' else 'none','krc':('KRC'+secrets.token_hex(5).upper()) if role=='student' else None,'registration_date':'2025-01-01' if role=='student' else None,'university':'TEST university' if role=='student' else '', 'research_field':'TEST medicine' if role=='student' else '', 'avatar_id':None,'created_at':datetime.now(timezone.utc).isoformat()}
        db.users.insert_one({**row,'password_hash':bcrypt.hashpw(hashlib.sha256(c['password'].encode()).digest(),bcrypt.gensalt()).decode()});c['accounts'][role]=row;save(c)
        if role in ('admin','visitor','student'):
            s=requests.Session();s.headers.update({'X-Kura-Request':'1','Origin':BASE});r=s.post(BASE+'/api/auth/login',json={'email':row['email'],'password':c['password']},timeout=60);assert r.status_code==200,r.text;c['cookies'][role]=s.cookies.get_dict();save(c)
    cat=ok(c,'admin','post','/admin/categories',{'name':c['tag']+' category'});c['ids']['category']=cat['id'];c['category_ids'].append(cat['id']);save(c)
    c['title']=c['tag']+' '+('عنوانكورسطويل'*11);assert 143<=len(c['title'].split(' ',1)[1])<=180 and len(c['title'])<=180
    course(c,'long',c['title']);course(c,'normal',flag=True);course(c,'archive_course');course(c,'archive_lecture');save(c)
    import imageio_ffmpeg
    video=ROOT/'TEST_fixture.mp4'
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-f','lavfi','-i','testsrc=size=320x180:rate=24','-t','8','-c:v','libx264','-pix_fmt','yuv420p','-movflags','+faststart',str(video)],check=True,capture_output=True)
    c['video_size']=video.stat().st_size
    f=upload(c,'admin','lecture',c['ids']['normal'],'TEST_fixture.mp4',video.read_bytes());c['ids']['video_file']=f['id'];save(c)
    l=ok(c,'admin','post','/admin/courses/'+c['ids']['normal']+'/lectures',{'title':'TEST real video lecture','file_id':f['id']});c['ids']['video_lecture']=l['id'];save(c)
    f=upload(c,'admin','lecture',c['ids']['archive_lecture'],'TEST_archive.txt',b'TEST archive content');l=ok(c,'admin','post','/admin/courses/'+c['ids']['archive_lecture']+'/lectures',{'title':'TEST archive lecture','file_id':f['id']});c['ids']['archive_lid']=l['id'];save(c)
    p=ok(c,'visitor','post','/courses/'+c['ids']['long']+'/purchase');c['ids']['approved_purchase']=p['id'];save(c)
    f=upload(c,'visitor','receipt',p['id'],'TEST_receipt.png',png());ok(c,'visitor','post','/purchases/'+p['id']+'/receipt',{'file_id':f['id']});ok(c,'admin','post','/admin/purchases/'+p['id']+'/review',{'decision':'approved'});save(c)
    with open('/app/memory/test_credentials.md','a') as stream:stream.write('\nIteration 6: isolated TEST_FIX accounts active only during targeted testing; credentials in mode-0600 fixes/private_state.json. No owner account used.\n')
    print('Isolated fixtures prepared',c['tag'])
def cleanup():
    c=load();db=c['db'];uids=[a['id'] for a in c['accounts'].values()]
    assert all(db.users.find_one({'id':u,'name':{'$regex':'^'+c['tag']}}) for u in uids)
    counts={}
    for col,query in [('sessions',{'user_id':{'$in':uids}}),('reset_tokens',{'user_id':{'$in':uids}}),('files',{'owner_id':{'$in':uids}}),('purchases',{'user_id':{'$in':uids}}),('lectures',{'course_id':{'$in':c['course_ids']}}),('courses',{'id':{'$in':c['course_ids']}}),('categories',{'id':{'$in':c['category_ids']}}),('audit',{'user_id':{'$in':uids}}),('users',{'id':{'$in':uids}})]:counts[col]=db[col].delete_many(query).deleted_count
    checks={k+'_exact':json_util.dumps(list(db[k].find({})),sort_keys=True)==value for k,value in c['original'].items()}
    checks['users_removed']=db.users.count_documents({'id':{'$in':uids}})==0
    (ROOT/'cleanup.json').write_text(json.dumps({'deleted':counts,'checks':checks,'storage':'Metadata access revoked; physical provider objects retained (no delete API).'},indent=2));assert all(checks.values()),checks
    STATE.unlink()
    with open('/app/memory/test_credentials.md','a') as stream:stream.write('Iteration 6 complete: all temporary users/sessions/fixtures and private credentials removed by exact IDs. Original settings/courses/owner invitations exactly preserved. No deployment or mail.\n')
    print('Cleanup verified',checks)
if __name__=='__main__':
    import sys
    cleanup() if '--cleanup' in sys.argv else setup()