# Targeted research cancellation privacy, legacy serialization, and long-title payment regression.
import os, json, secrets, hashlib, io
from pathlib import Path
from datetime import datetime, timezone
import bcrypt, pytest, requests
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import json_util
from PIL import Image

load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')
BASE = os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
STATE = Path('/app/test_reports/privacy_layout_state.json')

def save(c):
    STATE.write_text(json.dumps({k:v for k,v in c.items() if k not in ('db','sessions')}))
    STATE.chmod(0o600)

def api(c, role, method, path, data=None, **kwargs):
    r=c['sessions'][role].request(method,BASE+'/api'+path,json=data,timeout=180,**kwargs)
    assert r.status_code==200,(path,r.status_code,r.text)
    return r.json()

def action(c,role,rid,act,note=''):
    return api(c,role,'post',f'/research/{rid}/action',{'action':act,'note':note})

def create(c,title):
    p={'title':title,'description':'TEST تفاصيل بحثية منزوعة الهوية للتحقق من الخصوصية والتنسيق.','research_field':'TEST الطب','service_type':'analysis','privacy_consent':True}
    row=api(c,'owner','post','/research',p)
    c['request_ids'].append(row['id']);save(c)
    assert api(c,'owner','get','/research/'+row['id'])['title']==title
    return row['id']

def quote_claim(c,rid):
    api(c,'owner','post',f'/research/{rid}/submit')
    q=api(c,'admin','post',f'/research/{rid}/quote',{'amount':'987.65','scope':'TEST تحليل البيانات وتقرير نهائي ضمن النطاق المتفق عليه','delivery_days':7})['quote']
    api(c,'owner','post',f'/research/{rid}/quote-decision',{'quote_id':q['id'],'decision':'accepted'})
    action(c,'employee',rid,'claim')
    return q

@pytest.fixture(scope='module')
def c():
    db=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    tag='TEST_PRIVACY_'+secrets.token_hex(5)
    password=secrets.token_urlsafe(24)
    c={'db':db,'sessions':{},'tag':tag,'password':password,'accounts':{},'request_ids':[], 'markers':[],
       'title':'دراسةبحثيةطويلة'*10,'filename':'TEST_'+('اسمملفطويل'*14)+'.txt',
       'original_settings':db.settings.find_one({'id':'site'},{'_id':0}),
       'original_invites':json_util.dumps(list(db.owner_invites.find({})),sort_keys=True),
       'original_courses':json_util.dumps(list(db.courses.find({})),sort_keys=True)}
    for role in ('admin','owner','employee'):
        uid=secrets.token_hex(12)
        user={'id':uid,'name':tag+'_'+role,'email':tag.lower()+role+'@example.com','phone':'+1999'+str(secrets.randbelow(90000000)+10000000),
              'role':'visitor' if role=='owner' else role,'status':'active','is_student':False,'university':'','research_field':'','krc':None,'registration_date':None,
              'student_status':'none','avatar_id':None,'created_at':datetime.now(timezone.utc).isoformat(),
              'password_hash':bcrypt.hashpw(hashlib.sha256(password.encode()).digest(),bcrypt.gensalt()).decode()}
        db.users.insert_one(user)
        c['accounts'][role]={'id':uid,'email':user['email'],'name':user['name'],'phone':user['phone']}
        save(c)
        s=requests.Session();s.headers.update({'X-Kura-Request':'1','Origin':BASE});c['sessions'][role]=s
        assert api(c,role,'post','/auth/login',{'email':user['email'],'password':password})['id']==uid
    settings=c['original_settings']
    # Only temporarily fill absent financial configuration, restoring its exact snapshot at cleanup.
    edits={}
    if not settings['currency']:edits['currency']='USD'
    if not settings['payment_instructions'].strip():edits['payment_instructions']='TEST external payment instructions'
    if edits:db.settings.update_one({'id':'site'},{'$set':edits})
    c['currency']=db.settings.find_one({'id':'site'})['currency'];save(c)
    yield c
    save(c)  # Browser checks use these isolated fixtures, then explicit cleanup removes all.

def assert_private(c,row):
    text=json.dumps(row,ensure_ascii=False)
    for marker in c['markers']+[c['accounts']['owner'][k] for k in ('id','email','name','phone')]:
        assert marker not in text, 'Private marker leaked: '+marker
    assert c['currency'] not in text
    assert not {'quote','quotes','receipts','paid_minor','accepted_quote','owner','owner_id','cancellation_resolution','cancel_note'} & row.keys()
    for e in row.get('events',[]):assert set(e)=={'id','action','actor_label','created_at','note'}

def test_01_current_cancellation_private_note(c):
    rid=create(c,c['title']);c['rid']=rid
    r=c['sessions']['owner'].post(BASE+'/api/files',data={'purpose':'research_input','context_id':rid},files={'file':(c['filename'],b'TEST private input','text/plain')},timeout=180)
    assert r.status_code==200,r.text
    c['input_id']=r.json()['id'];save(c)
    q=quote_claim(c,rid);c['markers'] += ['987.65','98765','135.79','13579','851.86','85186']
    owner_note=c['tag']+' OWNER_CANCEL_PRIVATE 135.79 '+c['currency']
    note=c['tag']+' ADMIN_SETTLEMENT_PRIVATE quote 987.65 paid 135.79 remaining 851.86 '+c['currency']
    c['markers'] += [owner_note,note,'OWNER_CANCEL_PRIVATE','ADMIN_SETTLEMENT_PRIVATE'];c['note']=note
    action(c,'owner',rid,'cancel',owner_note)
    action(c,'admin',rid,'reject_cancel',note)
    employee=api(c,'employee','get',f'/research/{rid}')
    assert_private(c,employee)
    assert all(e['note']=='' for e in employee['events'] if e['action'] in ('cancel','reject_cancel'))
    for role in ('owner','admin'):
        row=api(c,role,'get',f'/research/{rid}')
        assert row['cancellation_resolution']==note and any(e['note']==note for e in row['events'])
    stored=c['db'].research_requests.find_one({'id':rid})
    assert all(e['financial'] is True for e in stored['events'] if e['action'] in ('cancel','reject_cancel'))
    save(c)

@pytest.mark.parametrize('action_name',['cancel','approve_cancel','reject_cancel'])
@pytest.mark.parametrize('legacy_flag',[False,None])
def test_02_legacy_cancellation_projection(c,action_name,legacy_flag):
    marker=c['tag']+'_'+action_name+'_'+str(legacy_flag)+'_PRIVATE_2468.13'
    ev={'id':secrets.token_hex(12),'action':action_name,'actor_label':'الإدارة','actor_id':c['accounts']['owner']['id'],'created_at':datetime.now(timezone.utc).isoformat(),
        'note':marker,'amount_minor':246813,'currency':marker,'extra':{'owner_email':c['accounts']['owner']['email'],'private':marker}}
    if legacy_flag is not None:ev['financial']=legacy_flag
    c['db'].research_requests.update_one({'id':c['rid'],'owner_id':c['accounts']['owner']['id']},{'$push':{'events':ev}})
    c['markers'].append(marker);save(c)
    row=api(c,'employee','get',f'/research/{c["rid"]}')
    assert_private(c,row)
    safe=next(e for e in row['events'] if e['id']==ev['id'])
    assert safe['note']=='' and safe['action']==action_name
    assert marker in json.dumps(api(c,'owner','get',f'/research/{c["rid"]}'))

def test_03_unknown_quote_receipt_history_blocked(c):
    events=[]
    for name in ['future_financial_settlement','quote_sent','quote_rejected','quote_accepted','receipt_submitted','receipt_approved','receipt_rejected']:
        for flag in (False,None):
            marker=c['tag']+'_'+name+'_'+str(flag)+'_FINANCIAL_PRIVATE'
            ev={'id':secrets.token_hex(12),'action':name,'note':marker,'actor_label':'الإدارة','created_at':datetime.now(timezone.utc).isoformat(),'extra_finance':marker}
            if flag is not None:ev['financial']=flag
            c['markers'].append(marker);events.append(ev)
    c['db'].research_requests.update_one({'id':c['rid'],'owner_id':c['accounts']['owner']['id']},{'$push':{'events':{'$each':events}}})
    row=api(c,'employee','get',f'/research/{c["rid"]}');assert_private(c,row)
    assert not {e['id'] for e in events}&{e['id'] for e in row['events']}
    save(c)

def test_04_approve_and_early_cancel_financial_flags(c):
    for label,claimed in [('approve',True),('early',False)]:
        rid=create(c,c['tag']+' '+label)
        if claimed:quote_claim(c,rid)
        action(c,'owner',rid,'cancel',c['tag']+' private cancellation')
        if claimed:action(c,'admin',rid,'approve_cancel',c['tag']+' PRIVATE_EXTERNAL_SETTLEMENT')
        row=api(c,'owner','get',f'/research/{rid}');assert row['status']=='cancelled'
        events=c['db'].research_requests.find_one({'id':rid})['events']
        assert all(e['financial'] is True for e in events if e['action'] in ('cancel','approve_cancel'))
        if claimed:
            r=c['sessions']['employee'].get(BASE+'/api/research/'+rid,timeout=60)
            assert r.status_code==404 and 'detail' in r.json()

def test_05_start_deliver_payment_file_and_privacy(c):
    rid=c['rid'];action(c,'employee',rid,'start')
    r=c['sessions']['employee'].post(BASE+'/api/files',data={'purpose':'research_result','context_id':rid},files={'file':('TEST_result.txt',b'TEST result','text/plain')},timeout=180)
    assert r.status_code==200,r.text
    result=r.json()['id'];c['result_id']=result
    action(c,'employee',rid,'deliver')
    row=api(c,'owner','get',f'/research/{rid}');assert row['status']=='ready_payment' and row['result_files']==[]
    denied=c['sessions']['owner'].get(BASE+'/api/files/'+result,timeout=60);assert denied.status_code==403 and 'detail' in denied.json()
    b=io.BytesIO();Image.new('RGB',(2,2),'blue').save(b,'PNG')
    for amount,paid,state in [('135.79',13579,'ready_payment'),('851.86',98765,'delivered')]:
        r=c['sessions']['owner'].post(BASE+'/api/files',data={'purpose':'research_receipt','context_id':rid},files={'file':('TEST_receipt.png',b.getvalue(),'image/png')},timeout=180)
        assert r.status_code==200,r.text
        fid=r.json()['id']
        rec=api(c,'owner','post',f'/research/{rid}/receipts',{'file_id':fid,'amount':amount})['receipts'][-1]
        api(c,'admin','post',f'/research/{rid}/review-receipt',{'receipt_id':rec['id'],'decision':'approved','reason':c['tag']+' RECEIPT_PRIVATE'})
        c['markers'].append(c['tag']+' RECEIPT_PRIVATE')
        owner=api(c,'owner','get',f'/research/{rid}');assert owner['paid_minor']==paid and owner['status']==state
        assert_private(c,api(c,'employee','get',f'/research/{rid}'))
        denied=c['sessions']['employee'].get(BASE+'/api/files/'+fid,timeout=60);assert denied.status_code==403 and 'detail' in denied.json()
    r=c['sessions']['owner'].get(BASE+'/api/files/'+result,timeout=60);assert r.status_code==200 and r.content==b'TEST result'
    payments=api(c,'owner','get','/my/research-payments');row=next(x for x in payments['items'] if x['id']==rid)
    assert row['title']==c['title'] and row['paid_minor']==98765 and row['remaining_minor']==0
    save(c)