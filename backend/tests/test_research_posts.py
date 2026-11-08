# Research/posts regression: isolated real API/storage workflows, no provider mocks.
import os, sys, io, json, secrets
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pytest, requests
from dotenv import load_dotenv
from pymongo import MongoClient
from PIL import Image

load_dotenv('/app/frontend/.env')
load_dotenv('/app/backend/.env')
BASE=os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
STATE=Path('/app/test_reports/research_test_state.json')

def png():
    b=io.BytesIO();Image.new('RGB',(80,60),'#155bea').save(b,'PNG');return b.getvalue()

@pytest.fixture(scope='session')
def c():
    db=MongoClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    tag='TEST_'+secrets.token_hex(5); password=secrets.token_urlsafe(20)
    x={'db':db,'tag':tag,'password':password,'accounts':{},'ids':{},'original':db.settings.find_one({'id':'site'},{'_id':0}), 'course_states':list(db.courses.find({}, {'_id':0,'id':1,'published':1}))}
    for role in ['admin','student','visitor','employee1','employee2']:
        s=requests.Session();s.headers.update({'X-Kura-Request':'1','Origin':BASE})
        payload={'name':tag+' '+role,'email':tag.lower()+role+'@example.com','phone':'+1999'+str(secrets.randbelow(90000000)+10000000),'password':password}
        if role=='student':payload.update(is_student=True,krc='KRC'+tag[5:],university='TEST university',research_field='TEST medicine',registration_date='2025-01-01')
        r=s.post(BASE+'/api/auth/register',json=payload,timeout=60);assert r.status_code==200,r.text
        x['accounts'][role]={'session':s,'id':r.json()['id'],'email':payload['email']}
        if role=='admin':db.users.update_one({'id':r.json()['id']},{'$set':{'role':'admin'}})
        elif role.startswith('employee'):db.users.update_one({'id':r.json()['id']},{'$set':{'role':'employee'}})
    ok(x,'admin','patch','/admin/users/'+x['accounts']['student']['id'],{'student_decision':'approved'})
    settings={**x['original']}
    if not settings['currency']:settings['currency']='USD'
    if not settings['payment_instructions'].strip():settings['payment_instructions']='TEST external payment instructions'
    if settings!=x['original']:ok(x,'admin','put','/admin/settings',settings)
    save(x)
    yield x
    save(x)  # Explicit cleanup after browser checks; retained only isolated fixtures.

def save(c):
    d={k:v for k,v in c.items() if k not in ('db','accounts')}
    d['accounts']={k:{a:b for a,b in v.items() if a!='session'} for k,v in c['accounts'].items()}
    STATE.write_text(json.dumps(d));STATE.chmod(0o600)

def call(c,who,method,path,**kwargs):
    return (c['accounts'][who]['session'] if who else requests).request(method,BASE+'/api'+path,timeout=180,**kwargs)

def ok(c,who,method,path,data=None):
    r=call(c,who,method,path,**({'json':data} if data is not None else {}));assert r.status_code==200,(path,r.status_code,r.text);return r.json()

def denied(c,who,method,path,code,data=None):
    r=call(c,who,method,path,**({'json':data} if data is not None else {}));assert r.status_code==code,(path,r.status_code,r.text);assert 'detail' in r.json()

def upload(c,who,purpose,rid='',ext='txt',body=None):
    r=call(c,who,'post','/files',data={'purpose':purpose,'context_id':rid},files={'file':('TEST_ملف_بحث_طويل_للتحقق.'+ext,body if body is not None else (png() if ext=='png' else b'TEST research content'))})
    assert r.status_code==200,r.text;return r.json()['id']

def create(c,who='student',label='main'):
    p={'title':c['tag']+' '+label+' بحث خاص','description':'TEST وصف خاص ومفصل للطلب البحثي لا يطلع عليه غير صاحب الصلاحية','research_field':'TEST الصحة العامة','service_type':'analysis','privacy_consent':True}
    r=ok(c,who,'post','/research',p);c['ids'][label]=r['id'];assert ok(c,who,'get','/research/'+r['id'])['title']==p['title'];save(c);return r['id']

def quoted(c,rid,who='student',amount='100.00'):
    ok(c,who,'post',f'/research/{rid}/submit')
    q=ok(c,'admin','post',f'/research/{rid}/quote',{'amount':amount,'scope':'TEST تحليل البيانات وتسليم تقرير نهائي ضمن جولة تعديل واحدة','delivery_days':7})['quote']
    ok(c,who,'post',f'/research/{rid}/quote-decision',{'quote_id':q['id'],'decision':'accepted'})
    return q

def receipt(c,rid,amount,who='student'):
    fid=upload(c,who,'research_receipt',rid,'png')
    r=ok(c,who,'post',f'/research/{rid}/receipts',{'file_id':fid,'amount':amount});return r['receipts'][-1]

def review(c,rid,rec,decision='approved',reason=''):
    return ok(c,'admin','post',f'/research/{rid}/review-receipt',{'receipt_id':rec['id'],'decision':decision,'reason':reason})

def test_01_health_auth_mutation(c):
    assert ok(c,None,'get','/health')=={'status':'ok','phase':1}
    denied(c,None,'get','/research',401)
    r=call(c,'visitor','post','/research',headers={'X-Kura-Request':''},json={});assert r.status_code==403 and 'detail' in r.json()

def test_02_draft_validation_edit_privacy(c):
    rid=create(c)
    assert ok(c,'student','get','/research/'+rid)['status']=='draft'
    assert rid not in [r['id'] for r in ok(c,'admin','get','/research')['items']]
    assert rid not in [r['id'] for r in ok(c,'visitor','get','/research')['items']]
    denied(c,'visitor','get','/research/'+rid,404)
    for bad in [{'title':'a'},{'description':'short'},{'research_field':'a'},{'privacy_consent':False}]:
        p={'title':'TEST valid title','description':'TEST valid description long enough','research_field':'TEST medicine','privacy_consent':True,**bad}
        denied(c,'student','post','/research',422,p)
    p={'title':c['tag']+' edited private title','description':'TEST updated research description long enough','research_field':'TEST طب','privacy_consent':True}
    ok(c,'student','put','/research/'+rid,p)
    assert ok(c,'student','get','/research/'+rid)['title']==p['title']

def test_03_input_real_upload_limits_remove(c):
    rid=c['ids']['main'];fid=upload(c,'student','research_input',rid);c['ids']['input']=fid
    assert ok(c,'student','get','/research/'+rid)['input_files'][0]['id']==fid
    assert ok(c,'student','get','/files/'+fid+'/metadata')['original_filename'].endswith('.txt')
    assert call(c,'student','get','/files/'+fid).content==b'TEST research content'
    denied(c,'visitor','get','/files/'+fid+'/metadata',403)
    for ext,body,code in [('mp4',b'0000ftyp',422),('txt',b'x'*(25*1024*1024+1),413)]:
        r=call(c,'student','post','/files',data={'purpose':'research_input','context_id':rid},files={'file':('TEST.'+ext,body)});assert r.status_code==code and 'detail' in r.json()
    removed=upload(c,'student','research_input',rid)
    assert ok(c,'student','delete',f'/research/{rid}/attachments/{removed}')['success']
    denied(c,'student','get','/files/'+removed+'/metadata',404)
    ok(c,'student','post',f'/research/{rid}/submit')
    assert ok(c,'admin','get','/research',)['items'][0]['status']=='waiting_quote'

def test_04_quotes_discount_reject_stale_lock(c):
    rid=c['ids']['main'];payload={'amount':'100.01','scope':'TEST scope accepted for this request','delivery_days':7}
    for amount in ['NaN','0','1.234','-1']:
        denied(c,'admin','post',f'/research/{rid}/quote',422,{**payload,'amount':amount})
    q=ok(c,'admin','post',f'/research/{rid}/quote',payload)['quote'];assert q['amount_minor']==8501 and q['discount_percent']==15
    denied(c,'student','post',f'/research/{rid}/quote-decision',422,{'quote_id':q['id'],'decision':'rejected'})
    ok(c,'student','post',f'/research/{rid}/quote-decision',{'quote_id':q['id'],'decision':'rejected','reason':'TEST clarify scope'})
    assert ok(c,'student','get','/research/'+rid)['quotes'][0]['reason']=='TEST clarify scope'
    new=ok(c,'admin','post',f'/research/{rid}/quote',{**payload,'amount':'100.00'})['quote']
    denied(c,'student','post',f'/research/{rid}/quote-decision',409,{'quote_id':q['id'],'decision':'accepted'})
    ok(c,'student','post',f'/research/{rid}/quote-decision',{'quote_id':new['id'],'decision':'accepted'})
    row=ok(c,'student','get','/research/'+rid);assert row['status']=='available' and row['payment_status']=='unpaid'
    denied(c,'admin','post',f'/research/{rid}/quote',409,payload)
    denied(c,'student','delete',f'/research/{rid}/attachments/{c["ids"]["input"]}',409)

def test_05_non_sensitive_available_and_claim_race(c):
    rid=c['ids']['main'];rows=ok(c,'employee1','get','/research?scope=available')['items'];r=next(r for r in rows if r['id']==rid)
    assert r['title']=='دعم بحثي' and not {'owner_id','description','quote','receipts','input_files','result_files','accepted_quote'}&r.keys()
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda who:(who,call(c,who,'post',f'/research/{rid}/action',json={'action':'claim'})),['employee1','employee2']))
    assert sorted(r.status_code for _,r in results)==[200,409]
    c['worker']=next(w for w,r in results if r.status_code==200);c['otherworker']='employee2' if c['worker']=='employee1' else 'employee1';save(c)
    worker=ok(c,c['worker'],'get','/research/'+rid);assert worker['input_files'][0]['id']==c['ids']['input'] and not {'owner_id','quote','receipts','paid_minor','accepted_quote','owner'}&worker.keys()
    denied(c,c['otherworker'],'get','/research/'+rid,404)
    denied(c,c['otherworker'],'get','/files/'+c['ids']['input']+'/metadata',403)

def test_06_return_reassignment_revokes(c):
    rid=c['ids']['main'];w=c['worker'];old=upload(c,w,'research_result',rid);c['ids']['oldresult']=old
    denied(c,w,'post',f'/research/{rid}/action',422,{'action':'return'})
    ok(c,w,'post',f'/research/{rid}/action',{'action':'return','note':'TEST return explanation'})
    denied(c,w,'get','/files/'+old+'/metadata',403)
    denied(c,w,'get','/files/'+c['ids']['input']+'/metadata',403)
    ok(c,c['otherworker'],'post',f'/research/{rid}/action',{'action':'claim'})
    ok(c,'admin','post',f'/research/{rid}/action',{'action':'reopen_assignment','note':'TEST reassign'})
    denied(c,c['otherworker'],'get','/files/'+old+'/metadata',403)
    ok(c,w,'post',f'/research/{rid}/action',{'action':'claim'})

def test_07_unpaid_work_results_withheld(c):
    rid=c['ids']['main'];w=c['worker'];ok(c,w,'post',f'/research/{rid}/action',{'action':'start'})
    fid=upload(c,w,'research_result',rid);c['ids']['result']=fid
    ok(c,w,'post',f'/research/{rid}/action',{'action':'deliver'})
    row=ok(c,'student','get','/research/'+rid);assert row['status']=='ready_payment' and row['result_files']==[] and row['results_locked'] and 'released_file_ids' not in row
    denied(c,'student','get','/files/'+fid+'/metadata',403)
    denied(c,'student','get','/files/'+fid,403)
    denied(c,'student','post',f'/research/{rid}/action',409,{'action':'complete'})

def test_08_reject_replace_partial_full_immutable(c):
    rid=c['ids']['main'];rec=receipt(c,rid,'25')
    denied(c,'student','post',f'/research/{rid}/receipts',409,{'file_id':rec['file_id'],'amount':'25'})
    denied(c,'admin','post',f'/research/{rid}/review-receipt',422,{'receipt_id':rec['id'],'decision':'rejected'})
    review(c,rid,rec,'rejected','TEST unreadable')
    denied(c,'student','post',f'/research/{rid}/receipts',409,{'file_id':rec['file_id'],'amount':'25'})
    rec2=receipt(c,rid,'25');row=review(c,rid,rec2);assert row['paid_minor']==2500 and row['status']=='ready_payment'
    denied(c,'student','get','/files/'+c['ids']['result']+'/metadata',403)
    denied(c,'admin','post',f'/research/{rid}/review-receipt',409,{'receipt_id':rec2['id'],'decision':'approved'})
    fid=upload(c,'student','research_receipt',rid,'png')
    for amt in ['0','-1','60.01']:
        denied(c,'student','post',f'/research/{rid}/receipts',422,{'file_id':fid,'amount':amt})
    rec3=ok(c,'student','post',f'/research/{rid}/receipts',{'file_id':fid,'amount':'60'})['receipts'][-1]
    review(c,rid,rec3)
    row=ok(c,'student','get','/research/'+rid);assert row['status']=='delivered' and row['payment_status']=='paid' and row['paid_minor']==8500 and len(row['receipts'])==3 and row['receipts'][0]['reason']=='TEST unreadable'
    assert call(c,'student','get','/files/'+c['ids']['result']).content==b'TEST research content'

def test_09_revision_completion(c):
    rid=c['ids']['main'];w=c['worker']
    denied(c,'student','post',f'/research/{rid}/action',422,{'action':'revision'})
    ok(c,'student','post',f'/research/{rid}/action',{'action':'revision','note':'TEST requested revision'})
    denied(c,w,'post',f'/research/{rid}/action',422,{'action':'deliver'})
    fid=upload(c,w,'research_result',rid);row=ok(c,w,'post',f'/research/{rid}/action',{'action':'deliver'});assert row['status']=='delivered'
    assert any(f['id']==fid and f['revision']==1 for f in ok(c,'student','get','/research/'+rid)['result_files'])
    denied(c,'student','post',f'/research/{rid}/action',409,{'action':'revision','note':'TEST second revision'})
    ok(c,'student','post',f'/research/{rid}/action',{'action':'complete'});assert ok(c,'student','get','/research/'+rid)['status']=='completed'

def test_10_visitor_prepay_deliver_cancel_settlement(c):
    rid=create(c,'visitor','prepay');q=quoted(c,rid,'visitor','12.34');assert q['discount_percent']==0 and q['amount_minor']==1234
    rec=receipt(c,rid,'12.34','visitor');review(c,rid,rec)
    ok(c,'employee1','post',f'/research/{rid}/action',{'action':'claim'})
    denied(c,'employee1','post',f'/research/{rid}/action',422,{'action':'deliver'})
    fid=upload(c,'employee1','research_result',rid);ok(c,'employee1','post',f'/research/{rid}/action',{'action':'deliver'})
    assert call(c,'visitor','get','/files/'+fid).content==b'TEST research content'
    ok(c,'visitor','post',f'/research/{rid}/action',{'action':'cancel','note':'TEST request cancellation after work'})
    assert ok(c,'visitor','get','/research/'+rid)['cancel_requested']
    ok(c,'admin','post',f'/research/{rid}/action',{'action':'reject_cancel','note':'TEST discuss settlement first'})
    ok(c,'visitor','post',f'/research/{rid}/action',{'action':'cancel','note':'TEST confirm cancellation'})
    ok(c,'admin','post',f'/research/{rid}/action',{'action':'approve_cancel','note':'TEST refund 12.34 externally confirmed'})
    denied(c,'visitor','get','/files/'+fid,403)
    denied(c,'employee1','get','/files/'+fid+'/metadata',403)
    row=ok(c,'visitor','get','/research/'+rid);assert row['paid_minor']==1234 and len(row['receipts'])==1 and 'externally' in row['cancellation_resolution']
    sums=ok(c,'visitor','get','/my/research-payments');assert sums['items'][0]['settlement_required'] and sums['balances'][0]['remaining_minor']==0
    rid2=create(c,'visitor','earlycancel');ok(c,'visitor','post',f'/research/{rid2}/action',{'action':'cancel','note':'TEST early cancel'});assert ok(c,'visitor','get','/research/'+rid2)['status']=='cancelled'

def test_11_posts_actual_image_draft_publish_security(c):
    fid=upload(c,'admin','post_image','','png');c['ids']['postimage']=fid
    payload={'title':c['tag']+' منشور علمي','body':'TEST نص منشور علمي حقيقي للتحقق من العرض','image_id':fid,'published':False}
    p=ok(c,'admin','post','/admin/posts',payload);c['ids']['post']=p['id'];c['post_payload']=payload;save(c)
    denied(c,None,'get','/posts/'+p['id'],404);denied(c,None,'get','/post-images/'+fid,404)
    denied(c,'visitor','post','/admin/posts',403,payload)
    r=call(c,'visitor','post','/files',data={'purpose':'post_image'},files={'file':('TEST.png',png())});assert r.status_code==403
    ok(c,'admin','put','/admin/posts/'+p['id'],{**payload,'published':True});c['post_payload']['published']=True
    assert ok(c,None,'get','/posts/'+p['id'])['title']==payload['title']
    assert call(c,None,'get','/post-images/'+fid).content==png()
    private=upload(c,'visitor','avatar','','png')
    denied(c,'admin','put','/admin/posts/'+p['id'],422,{**payload,'published':True,'image_id':private})
    denied(c,None,'get','/post-images/'+private,404)
    for ext,content,code in [('png',b'x'*(5*1024*1024+1),413),('txt',b'TEST',422)]:
        r=call(c,'admin','post','/files',data={'purpose':'post_image'},files={'file':('TEST.'+ext,content)});assert r.status_code==code

def test_12_post_idempotent_likes_comments_authorization(c):
    pid=c['ids']['post'];path=f'/posts/{pid}'
    denied(c,None,'put',path+'/reaction',401,{'liked':True})
    denied(c,None,'post',path+'/comments',401,{'body':'TEST comment'})
    for _ in range(2):assert ok(c,'visitor','put',path+'/reaction',{'liked':True})['like_count']==1
    assert ok(c,'visitor','get',path)['liked']
    assert ok(c,'student','put',path+'/reaction',{'liked':True})['like_count']==2
    assert ok(c,'visitor','put',path+'/reaction',{'liked':False})['like_count']==1
    for body in ['   ','x'*1501]:denied(c,'visitor','post',path+'/comments',422,{'body':body})
    com=ok(c,'visitor','post',path+'/comments',{'body':'  <script>window.TEST_XSS=1</script> TEST تعليق  '});c['ids']['comment']=com['id'];assert com['body'].startswith('<script>')
    items=ok(c,None,'get',path+'/comments')['items'];assert items[0]['id']==com['id'] and not {'email','avatar_id','user_id'}&items[0].keys()
    denied(c,'student','delete',path+'/comments/'+com['id'],404)
    assert ok(c,'visitor','delete',path+'/comments/'+com['id'])['success']
    assert ok(c,None,'get',path+'/comments')['total']==0
    other=ok(c,'student','post',path+'/comments',{'body':'TEST admin moderated comment'})
    ok(c,'admin','delete',path+'/comments/'+other['id']);assert ok(c,None,'get',path+'/comments')['total']==0

def test_13_post_image_replace_hide_delete(c):
    pid=c['ids']['post'];old=c['ids']['postimage'];new=upload(c,'admin','post_image','','png');p={**c['post_payload'],'image_id':new};c['post_payload']=p
    ok(c,'admin','put','/admin/posts/'+pid,p);assert ok(c,None,'get','/posts/'+pid)['image_id']==new
    denied(c,None,'get','/post-images/'+old,404)
    ok(c,'admin','put','/admin/posts/'+pid,{**p,'published':False})
    denied(c,None,'get','/posts/'+pid+'/comments',404);denied(c,None,'get','/post-images/'+new,404)
    ok(c,'admin','put','/admin/posts/'+pid,p)
    clone=ok(c,'admin','post','/admin/posts',{**p,'title':c['tag']+' disposable','image_id':None})
    ok(c,'admin','delete','/admin/posts/'+clone['id']);denied(c,None,'get','/posts/'+clone['id'],404);denied(c,None,'get','/posts/'+clone['id']+'/comments',404)

def test_14_blocked_user_private_denial_public_read(c):
    uid=c['accounts']['visitor']['id'];c['db'].users.update_one({'id':uid},{'$set':{'status':'blocked'}})
    try:
        pid=c['ids']['post'];assert ok(c,'visitor','get','/posts/'+pid)['published']
        denied(c,'visitor','put',f'/posts/{pid}/reaction',403,{'liked':True})
        denied(c,'visitor','post',f'/posts/{pid}/comments',403,{'body':'TEST blocked'})
        denied(c,'visitor','get','/research',403)
        r=call(c,'visitor','post','/files',data={'purpose':'avatar'},files={'file':('TEST.png',png())});assert r.status_code==403
        denied(c,'visitor','get','/files/'+c['ids']['result'],403)
    finally:c['db'].users.update_one({'id':uid},{'$set':{'status':'active'}})

def test_15_counts_search_pagination_balances_audit(c):
    d=ok(c,'admin','get','/admin/operations-summary')
    assert d=={'waiting_quote':c['db'].research_requests.count_documents({'status':'waiting_quote'}),'research_receipts':c['db'].research_requests.count_documents({'payment_status':'pending','status':{'$ne':'cancelled'}}),'published_posts':c['db'].posts.count_documents({'published':True,'deleted':False})}
    d=ok(c,None,'get','/posts?q='+c['tag']);assert d['total']==1 and len(d['items'])==1
    assert ok(c,None,'get','/posts?q='+c['tag']+'&page=2')['items']==[]
    assert ok(c,'student','get','/research?page=2')['items']==[]
    balances=ok(c,'student','get','/my/research-payments')['balances'];assert balances[0]['paid_minor']==8500 and balances[0]['remaining_minor']==0
    actions={a['action'] for a in c['db'].audit.find({'target':c['ids']['main']})};assert {'research_created','research_claim','research_receipt_approved','research_complete'}<=actions

def test_16_course_receipt_file_regression(c):
    cat=ok(c,None,'get','/categories')[0]['id']
    p={'title':c['tag']+' regression course','description':'TEST regression description long enough','category_id':cat,'price':'10','free_for_students':False,'published':True}
    course=ok(c,'admin','post','/admin/courses',p);c['ids']['course']=course['id']
    fid=upload(c,'admin','lecture',course['id']);ok(c,'admin','post',f'/admin/courses/{course["id"]}/lectures',{'title':'TEST lecture','file_id':fid})
    purchase=ok(c,'student','post',f'/courses/{course["id"]}/purchase');assert purchase['amount_minor']==1000
    rec=upload(c,'student','receipt',purchase['id'],'png');ok(c,'student','post',f'/purchases/{purchase["id"]}/receipt',{'file_id':rec})
    denied(c,'visitor','get','/files/'+rec+'/metadata',403);denied(c,'student','get','/files/'+fid,403)
    ok(c,'admin','post',f'/admin/purchases/{purchase["id"]}/review',{'decision':'approved'})
    assert call(c,'student','get','/files/'+fid).content==b'TEST research content'
    assert ok(c,'student','get',f'/courses/{course["id"]}')['has_access']