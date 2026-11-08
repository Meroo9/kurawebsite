# Current full-site accounts/courses/security regression, preserving all original courses and invitations.
import secrets, io, hashlib
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
import requests
from bson import json_util
from PIL import Image
from full_site_support import setup, save, ok, denied, req, upload, png

@pytest.fixture(scope='module')
def c():
    x=setup();yield x;save(x)

def course(c,label,price='12.34',flag=False,published=True):
    p={'title':c['tag']+' '+label,'description':'TEST comprehensive medical education course','category_id':c['ids']['category'],'price':price,'free_for_students':flag,'published':published}
    row=ok(c,'admin','post','/admin/courses',p);c['course_ids'].append(row['id']);save(c);assert ok(c,'admin','get','/courses/'+row['id'])['title']==p['title'];return row,p

def test_01_health_public_and_role_gates(c):
    assert ok(c,None,'get','/health')=={'status':'ok','phase':1}
    assert ok(c,None,'get','/site')['currency']==c['currency']
    assert isinstance(ok(c,None,'get','/categories'),list)
    for role in (None,'visitor','pending','student','employee1','employee2'):
        for endpoint in ('users','courses','overview','purchases','audit','posts','operations-summary'):
            denied(c,role,'get','/admin/'+endpoint,401 if role is None else 403)

def test_02_cookie_csrf_cors(c):
    a=c['accounts']['visitor'];r=req(c,'visitor','post','/auth/login',json={'email':a['email'],'password':c['password']})
    assert r.json()['id']==a['id'];cookie=r.headers['Set-Cookie'];assert all(v in cookie for v in ('Secure','HttpOnly','Path=/api'))
    r=req(c,'visitor','post','/auth/logout',headers={'X-Kura-Request':''});assert r.status_code==403 and 'detail' in r.json()
    r=req(c,'visitor','post','/auth/logout',headers={'Origin':'https://hostile.example'});assert r.status_code==403
    r=req(c,None,'options','/auth/profile',headers={'Origin':'https://hostile.example','Access-Control-Request-Method':'PUT','Access-Control-Request-Headers':'X-Kura-Request'});assert r.status_code==400 and 'access-control-allow-origin' not in r.headers

def test_03_normalized_duplicates_and_dates(c):
    a=c['accounts']['visitor'];p={'name':'TEST duplicate','email':a['email'].upper(),'phone':'+19998887776','password':c['password']}
    denied(c,None,'post','/auth/register',409,p)
    denied(c,None,'post','/auth/register',409,{**p,'email':c['tag'].lower()+'dup@example.com','phone':'00'+a['phone'][1:]})
    student=ok(c,'pending','get','/auth/me')
    denied(c,None,'post','/auth/register',409,{**p,'email':c['tag'].lower()+'dup@example.com','is_student':True,'university':'TEST','research_field':'TEST','krc':' '+student['krc'].lower()+' ','registration_date':'2025-01-01'})
    profile={k:student[k] for k in ('name','phone','is_student','university','research_field','krc','registration_date')}
    for date in ('2099-01-01','2025-02-30',None):denied(c,'pending','put','/auth/profile',422,{**profile,'registration_date':date})

def test_04_profile_no_self_promotion_and_krc_correction(c):
    row=ok(c,'student','get','/auth/me');p={k:row[k] for k in ('name','phone','is_student','university','research_field','krc','registration_date')}
    denied(c,'student','put','/auth/profile',403,{**p,'krc':'KRCCHANGED'})
    changed=ok(c,'student','put','/auth/profile',{**p,'name':c['tag']+' updated student','role':'admin','status':'active'});assert changed['role']=='student'
    assert ok(c,'student','get','/auth/me')['name']==changed['name']
    krc='KRC'+secrets.token_hex(7).upper();uid=c['accounts']['pending']['id'];ok(c,'admin','patch','/admin/users/'+uid,{'krc':krc});assert ok(c,'pending','get','/auth/me')['krc']==krc
    denied(c,'admin','patch','/admin/users/'+c['accounts']['visitor']['id'],409,{'krc':krc})

def test_05_employee_management(c):
    p={'name':c['tag']+' managed employee','email':c['tag'].lower()+'managed@example.com','phone':'+1777'+str(secrets.randbelow(90000000)+10000000),'password':c['password']}
    denied(c,'visitor','post','/admin/employees',403,p)
    row=ok(c,'admin','post','/admin/employees',p);c['accounts']['managed']={'id':row['id'],'email':p['email'],'name':p['name'],'phone':p['phone'],'session':requests.Session()};save(c)
    assert row['role']=='employee';ok(c,'admin','patch','/admin/users/'+row['id'],{'name':c['tag']+' edited employee'})
    assert ok(c,'admin','get','/admin/users?q='+p['email'])['items'][0]['name']==c['tag']+' edited employee'

def test_06_catalog_category_publish_prerequisite(c):
    cat=ok(c,'admin','post','/admin/categories',{'name':c['tag']+' category'});c['ids']['category']=cat['id'];c['category_ids'].append(cat['id']);save(c)
    ok(c,'admin','put','/admin/categories/'+cat['id'],{'name':c['tag']+' renamed category'});assert next(x for x in ok(c,None,'get','/categories') if x['id']==cat['id'])['name'].endswith('renamed category')
    row,p=course(c,'flagged',flag=True,published=False);cid=row['id'];c['ids']['course']=cid;c['course_payload']=p;save(c)
    denied(c,None,'get','/courses/'+cid,404)
    settings=c['db'].settings.find_one({'id':'site'},{'_id':0})
    try:
        c['db'].settings.update_one({'id':'site'},{'$set':{'payment_instructions':''}})
        denied(c,'admin','put','/admin/courses/'+cid,422,{**p,'published':True})
        c['db'].settings.update_one({'id':'site'},{'$set':{'currency':''}})
        denied(c,'admin','put','/admin/courses/'+cid,422,{**p,'published':True,'price':'0'})
    finally:c['db'].settings.replace_one({'id':'site'},settings)
    ok(c,'admin','put','/admin/courses/'+cid,{**p,'published':True});c['course_payload']['published']=True
    assert ok(c,None,'get','/courses/'+cid)['price_minor']==1234
    denied(c,'admin','delete','/admin/categories/'+cat['id'],409)

def test_07_student_pending_free_flag_not_discount(c):
    cid=c['ids']['course'];assert not ok(c,'pending','get','/courses/'+cid)['has_access'];assert ok(c,'student','get','/courses/'+cid)['has_access']
    row,_=course(c,'unflagged',flag=False);c['ids']['unflagged']=row['id'];save(c)
    assert not ok(c,'student','get','/courses/'+row['id'])['has_access']
    assert ok(c,'student','post','/courses/'+row['id']+'/purchase')['amount_minor']==1234
    denied(c,'employee1','post','/courses/'+cid+'/purchase',403)

def test_08_lectures_upload_order_edit_protection(c):
    cid=c['ids']['course'];f=upload(c,'admin','lecture',cid);c['ids']['lecture_file']=f
    l=ok(c,'admin','post',f'/admin/courses/{cid}/lectures',{'title':'TEST lecture 1','file_id':f,'order':2});c['ids']['lecture']=l['id']
    f2=upload(c,'admin','lecture',cid);l2=ok(c,'admin','post',f'/admin/courses/{cid}/lectures',{'title':'TEST lecture 2','file_id':f2,'order':1});c['ids']['lecture2_file']=f2
    ok(c,'admin','put','/admin/lectures/'+l['id'],{'title':'TEST edited lecture','file_id':f,'order':3})
    public=ok(c,None,'get','/courses/'+cid);assert [x['id'] for x in public['lectures']]==[l2['id'],l['id']] and all('file_id' not in x for x in public['lectures'])
    for who in (None,'visitor','pending','employee1'):denied(c,who,'get','/files/'+f,401 if who is None else 403)
    assert req(c,'student','get','/files/'+f).content==b'TEST private lecture content';save(c)

def test_09_purchase_concurrent_receipt_pending(c):
    cid=c['ids']['course']
    with ThreadPoolExecutor(2) as pool:rows=list(pool.map(lambda _:req(c,'visitor','post','/courses/'+cid+'/purchase'),range(2)))
    assert all(r.status_code==200 for r in rows) and rows[0].json()['id']==rows[1].json()['id']
    p=rows[0].json();c['ids']['purchase']=p['id'];assert p['amount_minor']==1234 and p['currency']==c['currency']
    assert ok(c,'visitor','get','/my/purchases/course/'+cid)['purchase']['id']==p['id']
    f=upload(c,'visitor','receipt',p['id'],'png');c['ids']['receipt_file']=f;row=ok(c,'visitor','post',f'/purchases/{p["id"]}/receipt',{'file_id':f});assert row['status']=='pending'
    assert not ok(c,'visitor','get','/courses/'+cid)['has_access'];denied(c,'other','get','/files/'+f+'/metadata',403);save(c)

def test_10_reject_replacement_double_approval_unlock_all(c):
    pid=c['ids']['purchase'];cid=c['ids']['course']
    denied(c,'admin','post',f'/admin/purchases/{pid}/review',422,{'decision':'rejected'})
    ok(c,'admin','post',f'/admin/purchases/{pid}/review',{'decision':'rejected','reason':'TEST unreadable'})
    f=upload(c,'visitor','receipt',pid,'png');row=ok(c,'visitor','post',f'/purchases/{pid}/receipt',{'file_id':f});assert len(row['receipts'])==2 and row['receipts'][0]['reason']=='TEST unreadable'
    with ThreadPoolExecutor(2) as pool:rs=list(pool.map(lambda _:req(c,'admin','post',f'/admin/purchases/{pid}/review',json={'decision':'approved'}),range(2)))
    assert sorted(r.status_code for r in rs)==[200,409]
    assert ok(c,'visitor','get','/my/purchases/course/'+cid)['purchase']['status']=='approved'
    for key in ('lecture_file','lecture2_file'):assert req(c,'visitor','get','/files/'+c['ids'][key]).content==b'TEST private lecture content'

def test_11_price_edit_currency_history(c):
    cid=c['ids']['course'];before=ok(c,'visitor','get','/my/purchases/course/'+cid)['purchase'];ok(c,'admin','put','/admin/courses/'+cid,{**c['course_payload'],'price':'23.45'})
    after=ok(c,'visitor','get','/my/purchases/course/'+cid)['purchase'];assert after['amount_minor']==1234 and after['currency']==before['currency'] and after['payment_instructions']==before['payment_instructions']
    assert ok(c,None,'get','/courses/'+cid)['price_minor']==2345

def test_12_avatar_validation_replacement_private(c):
    f=upload(c,'visitor','avatar',ext='png');assert ok(c,'visitor','get','/auth/me')['avatar_id']==f
    newer=upload(c,'visitor','avatar',ext='png');c['ids']['avatar']=newer;assert ok(c,'visitor','get','/auth/me')['avatar_id']==newer;denied(c,'visitor','get','/files/'+f+'/metadata',404)
    denied(c,'other','get','/files/'+newer,403)
    for filename,body,code in [('TEST.jpg',png(),422),('TEST.png',b'bad',422),('TEST.exe',b'bad',422),('TEST.png',b'x'*(5*1024*1024+1),413)]:
        r=req(c,'visitor','post','/files',data={'purpose':'avatar'},files={'file':(filename,body)});assert r.status_code==code and 'detail' in r.json()
    save(c)

def test_13_ranges_metadata_and_pdf(c):
    f=c['ids']['lecture_file'];m=ok(c,'visitor','get','/files/'+f+'/metadata');assert set(m)=={'id','size','content_type','original_filename'} and m['size']==len(b'TEST private lecture content')
    for value,body in [('bytes=0-3',b'TEST'),('bytes=-7',b'content'),('bytes=5-',b'private lecture content')]:
        r=req(c,'visitor','get','/files/'+f,headers={'Range':value});assert r.status_code==206 and r.content==body
    for value in ('bytes=999-','bytes=8-2','bytes=','bytes=-0','bytes=0-1,4-5'):assert req(c,'visitor','get','/files/'+f,headers={'Range':value}).status_code==416
    row,_=course(c,'pdf upload');pid=ok(c,'other','post','/courses/'+row['id']+'/purchase')['id']
    r=req(c,'other','post','/files',data={'purpose':'receipt','context_id':pid},files={'file':('TEST.pdf',b'%PDF- invalid')});assert r.status_code==422
    buf=io.BytesIO();Image.new('RGB',(20,20),'white').save(buf,'PDF');fid=upload(c,'other','receipt',pid,'pdf',buf.getvalue());assert req(c,'other','get','/files/'+fid).content==buf.getvalue()

def test_14_library_and_purchase_pagination(c):
    for i in range(13):course(c,'Library '+str(i),price='0')
    a=ok(c,'visitor','get','/my/library?q='+c['tag']+' Library');b=ok(c,'visitor','get','/my/library?q='+c['tag']+' Library&page=2');assert a['total']==13 and len(a['items'])==12 and len(b['items'])==1 and not {r['id'] for r in a['items']}&{r['id'] for r in b['items']}
    assert ok(c,'visitor','get','/my/library?category=TEST_MISSING')['total']==0
    uid=c['accounts']['other']['id'];p=ok(c,'other','post','/courses/'+c['ids']['course']+'/purchase');c['ids']['other_purchase']=p['id']
    for i in range(16):c['db'].purchases.insert_one({**p,'id':secrets.token_hex(12),'course_id':'TEST_HISTORY_'+c['tag']+str(i),'course_title':c['tag']+' history','created_at':(datetime.now(timezone.utc)+timedelta(seconds=i+1)).isoformat()})
    first=ok(c,'other','get','/my/purchases');assert len(first['items'])==15 and p['id'] not in [x['id'] for x in first['items']]
    assert ok(c,'other','get','/my/purchases/course/'+c['ids']['course'])['purchase']['id']==p['id'];save(c)

def test_15_block_inactive_revocation_unblock_logout(c):
    for role in ('blocked','inactive'):
        denied(c,role,'get','/auth/me',401);denied(c,role,'post','/auth/login',403,{'email':c['accounts'][role]['email'],'password':c['password']})
    uid=c['accounts']['other']['id'];ok(c,'admin','patch','/admin/users/'+uid,{'status':'blocked'});denied(c,'other','get','/auth/me',401)
    ok(c,'admin','patch','/admin/users/'+uid,{'status':'active'});ok(c,'other','post','/auth/login',{'email':c['accounts']['other']['email'],'password':c['password']})
    assert ok(c,'other','post','/auth/logout')['success'];denied(c,'other','get','/auth/me',401)
    ok(c,'other','post','/auth/login',{'email':c['accounts']['other']['email'],'password':c['password']});save(c)

def test_16_reset_neutral_managed_mail_and_single_use(c):
    uid=c['accounts']['other']['id'];db=c['db'];assert not db.users.find_one({'email':'delivered@resend.dev'})
    missing=ok(c,None,'post','/auth/forgot-password',{'email':c['tag'].lower()+'missing@example.com'})
    original=c['accounts']['other']['email'];db.users.update_one({'id':uid},{'$set':{'email':'delivered@resend.dev'}})
    try:
        response=ok(c,None,'post','/auth/forgot-password',{'email':'delivered@resend.dev'});assert response==missing and db.reset_tokens.count_documents({'user_id':uid})==1
    finally:db.users.update_one({'id':uid},{'$set':{'email':original}})
    for expired in (True,False):
        token=secrets.token_urlsafe(40);db.reset_tokens.insert_one({'token_hash':hashlib.sha256(token.encode()).hexdigest(),'user_id':uid,'expires_at':datetime.now(timezone.utc)+timedelta(minutes=-1 if expired else 30)})
        if expired:denied(c,None,'post','/auth/reset-password',400,{'token':token,'password':c['password']})
        else:
            assert 'message' in ok(c,None,'post','/auth/reset-password',{'token':token,'password':c['password']});denied(c,'other','get','/auth/me',401);denied(c,None,'post','/auth/reset-password',400,{'token':token,'password':c['password']})
    ok(c,'other','post','/auth/login',{'email':original,'password':c['password']});save(c)

def test_17_archive_revokes_and_category_delete(c):
    row,_=course(c,'archive');f=upload(c,'admin','lecture',row['id']);l=ok(c,'admin','post',f'/admin/courses/{row["id"]}/lectures',{'title':'TEST archive lecture','file_id':f})
    ok(c,'admin','delete','/admin/lectures/'+l['id']);assert not ok(c,'admin','get','/courses/'+row['id'])['lectures'];denied(c,'student','get','/files/'+f,403)
    ok(c,'admin','delete','/admin/courses/'+row['id']);denied(c,None,'get','/courses/'+row['id'],404);denied(c,'student','get','/files/'+f,403)
    cat=ok(c,'admin','post','/admin/categories',{'name':c['tag']+' disposable'});c['category_ids'].append(cat['id']);save(c);ok(c,'admin','delete','/admin/categories/'+cat['id']);assert cat['id'] not in [x['id'] for x in ok(c,None,'get','/categories')]
    denied(c,'admin','put','/admin/categories/TEST_MISSING',404,{'name':'TEST missing'})

def test_18_balances_audit_original_preservation(c):
    assert ok(c,'visitor','get','/my/purchases')['balances']==[{'currency':c['currency'],'paid_minor':1234,'remaining_minor':0}]
    logs=ok(c,'admin','get','/admin/audit?q='+c['ids']['purchase']);assert {'purchase_created','receipt_rejected','receipt_approved'}<={x['action'] for x in logs['items']}
    original=json_util.loads(c['original_courses']);assert all(c['db'].courses.find_one({'id':row['id']})==row for row in original)
    assert json_util.dumps(list(c['db'].owner_invites.find({})),sort_keys=True)==c['original_invites']