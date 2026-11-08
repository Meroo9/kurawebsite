# Full-site pagination, employee legacy privacy, blocked permissions, and isolated UI evidence fixtures.
import secrets,json
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
import pytest
from full_site_support import STATE, save, load, ok, denied, req, upload
import test_research_posts as rp
rp.STATE=STATE
rp.save=save
from test_research_posts import create,quoted,receipt,review,upload as research_upload

@pytest.fixture(scope='module')
def c():
    x=load();yield x;save(x)

def test_01_public_posts_comments_pagination(c):
    posts=[]
    for i in range(7):posts.append(ok(c,'admin','post','/admin/posts',{'title':c['tag']+' Pagination '+str(i),'body':'TEST scientific content for pagination','published':True})['id'])
    c['ids']['pagination_post']=posts[0];save(c)
    one=ok(c,None,'get','/posts?q='+c['tag']+' Pagination');two=ok(c,None,'get','/posts?q='+c['tag']+' Pagination&page=2');assert len(one['items'])==6 and len(two['items'])==1 and one['total']==7
    for i in range(16):ok(c,'student','post',f'/posts/{posts[0]}/comments',{'body':'TEST comment '+str(i)})
    one=ok(c,None,'get',f'/posts/{posts[0]}/comments');two=ok(c,None,'get',f'/posts/{posts[0]}/comments?page=2');assert len(one['items'])==15 and len(two['items'])==1 and one['total']==16 and not {x['id'] for x in one['items']}&{x['id'] for x in two['items']}

def test_02_research_legacy_notes_and_assigned_layout(c):
    rid=create(c,'visitor','employee_layout');ok(c,'visitor','put','/research/'+rid,{'title':'دراسةبحثيةطويلة'*10,'description':'TEST long description for responsive research role permissions','research_field':'TEST الطب','privacy_consent':True,'service_type':'analysis'})
    fid=upload(c,'visitor','research_input',rid);c['ids']['layout_input']=fid;quoted(c,rid,'visitor','987.65');ok(c,'employee1','post',f'/research/{rid}/action',{'action':'claim'})
    marker=c['tag']+' PRIVATE_SETTLEMENT_98765';events=[]
    for act in ('cancel','approve_cancel','reject_cancel','quote_sent','receipt_approved','unknown_finance'):
        for flag in (False,None):
            e={'id':secrets.token_hex(12),'action':act,'actor_label':'الإدارة','created_at':datetime.now(timezone.utc).isoformat(),'note':marker,'owner_email':c['accounts']['visitor']['email'],'amount_minor':98765}
            if flag is not None:e['financial']=flag
            events.append(e)
    c['db'].research_requests.update_one({'id':rid,'owner_id':c['accounts']['visitor']['id']},{'$push':{'events':{'$each':events}}})
    emp=ok(c,'employee1','get','/research/'+rid);assert marker not in json.dumps(emp) and not {'owner','owner_id','receipts','paid_minor','accepted_quote','quote'}&emp.keys()
    for e in emp['events']:assert set(e)=={'id','action','actor_label','created_at','note'}
    assert marker in json.dumps(ok(c,'visitor','get','/research/'+rid)) and marker in json.dumps(ok(c,'admin','get','/research/'+rid))
    c['ids']['employee_layout']=rid;save(c)

def test_03_sensitive_pool_tampering_and_new_cancellation(c):
    rid=create(c,'pending','available_layout');q=quoted(c,rid,'pending','20');assert q['discount_percent']==0
    pool=ok(c,'employee2','get','/research?scope=available');row=next(r for r in pool['items'] if r['id']==rid);assert row['title']=='تحليل البيانات' and not {'description','owner_id','owner','quote','receipts','input_files'}&row.keys()
    denied(c,'visitor','post',f'/research/{rid}/submit',403);denied(c,'pending','post',f'/research/{rid}/action',403,{'action':'claim'})
    assigned=c['ids']['employee_layout'];ok(c,'visitor','post',f'/research/{assigned}/action',{'action':'cancel','note':c['tag']+' owner cancellation private'})
    note=c['tag']+' admin settlement 987.65';ok(c,'admin','post',f'/research/{assigned}/action',{'action':'reject_cancel','note':note})
    assert note not in json.dumps(ok(c,'employee1','get','/research/'+assigned));assert note==ok(c,'visitor','get','/research/'+assigned)['cancellation_resolution']
    denied(c,'employee2','get','/files/'+c['ids']['layout_input']+'/metadata',403)
    c['ids']['available_layout']=rid;save(c)

def test_04_employee_financial_api_roles_and_blocked_stale(c):
    rid=c['ids']['employee_layout']
    denied(c,'employee1','post',f'/research/{rid}/quote',403,{'amount':'1','scope':'TEST invalid worker pricing','delivery_days':1})
    denied(c,'employee1','post',f'/research/{rid}/receipts',403,{'file_id':'TEST_FAKE','amount':'1'})
    denied(c,'employee1','post',f'/research/{rid}/review-receipt',403,{'receipt_id':'TEST_FAKE','decision':'approved'})
    uid=c['accounts']['visitor']['id'];c['db'].users.update_one({'id':uid},{'$set':{'status':'blocked'}})
    try:
        for path in ('/research','/files/'+c['ids']['layout_input']+'/metadata'):denied(c,'visitor','get',path,403)
        denied(c,'visitor','put','/posts/'+c['ids']['post']+'/reaction',403,{'liked':True})
        denied(c,'visitor','post','/posts/'+c['ids']['post']+'/comments',403,{'body':'TEST blocked'})
        assert ok(c,'visitor','get','/posts/'+c['ids']['post'])['published']
    finally:c['db'].users.update_one({'id':uid},{'$set':{'status':'active'}})

def test_05_concurrent_research_receipt_review(c):
    rid=create(c,'visitor','race_review');quoted(c,rid,'visitor','10');r=receipt(c,rid,'10','visitor')
    with ThreadPoolExecutor(2) as pool:responses=list(pool.map(lambda _:req(c,'admin','post',f'/research/{rid}/review-receipt',json={'receipt_id':r['id'],'decision':'approved'}),range(2)))
    assert sorted(r.status_code for r in responses)==[200,409]
    row=ok(c,'visitor','get','/research/'+rid);assert row['paid_minor']==1000 and row['status']=='available';save(c)

def test_06_private_reference_images_and_invalid_inputs(c):
    pid=c['ids']['post'];post=ok(c,'admin','get','/posts/'+pid)
    for key in ('lecture_file','receipt_file','avatar'):
        fid=c['ids'][key];denied(c,None,'get','/post-images/'+fid,404);denied(c,'admin','put','/admin/posts/'+pid,422,{'title':post['title'],'body':post['body'],'published':True,'image_id':fid})
    denied(c,'admin','post','/admin/courses',422,{'title':'TEST invalid price','description':'TEST course description','category_id':c['ids']['category'],'price':'NaN','published':True})
    for path in ('/posts?page=0','/courses?page=0'):denied(c,None,'get',path,422)
    denied(c,'visitor','get','/research?page=0',422)

@pytest.mark.parametrize('resource',['courses','lectures'])
def test_07_missing_resource_delete_semantics(c,resource):
    # Nonexistent DELETE must report 404 rather than falsely confirming an archive.
    denied(c,'admin','delete','/admin/'+resource+'/TEST_NONEXISTENT',404)