# Final isolated long-content fixtures, multicurrency historical snapshots and original-data integrity.
import pytest
import secrets
from bson import json_util
from full_site_support import load, save, ok, denied

@pytest.fixture(scope='module')
def c():
    x=load();yield x;save(x)

def test_01_long_course_fixture_valid(c):
    cid=c['ids']['ui_course'];row=ok(c,'admin','get','/courses/'+cid);title=c['tag']+' '+('عنوانكورسطويل'*11)
    assert 140<=len('عنوانكورسطويل'*11)<=180
    ok(c,'admin','put','/admin/courses/'+cid,{'title':title,'description':row['description'],'category_id':row['category_id'],'price':str(row['price_minor']/100),'free_for_students':row['free_for_students'],'published':True})
    assert ok(c,None,'get','/courses/'+cid)['title']==title

def test_02_long_post_comment_fixture(c):
    title='منشورعلميطويل'*11
    post=ok(c,'admin','post','/admin/posts',{'title':title,'body':('محتوىعلميطويل'*100)+' <script>window.TEST_XSS=1</script>','published':True})
    c['ids']['long_post']=post['id'];c['post_ids'].append(post['id']);save(c)
    assert ok(c,None,'get','/posts/'+post['id'])['title']==title
    row=ok(c,'visitor','post','/posts/'+post['id']+'/comments',{'body':'  '+('تعليقعلميطويل'*100)+'  '})
    assert row['body']=='تعليقعلميطويل'*100
    assert ok(c,None,'get','/posts/'+post['id']+'/comments')['items'][0]['body']==row['body']

def test_03_multiple_currency_balances_isolated_history(c):
    # Explicit simulated legacy purchase row belonging only to a temporary account.
    source=ok(c,'visitor','get','/my/purchases/course/'+c['ids']['course'])['purchase'];currency='EUR' if c['currency']!='EUR' else 'USD'
    row={**source,'id':secrets.token_hex(12),'course_id':'TEST_LEGACY_'+c['tag'],'course_title':c['tag']+' legacy currency snapshot','currency':currency,'amount_minor':567,'status':'approved','receipts':[]}
    c['db'].purchases.insert_one(row)
    balances=ok(c,'visitor','get','/my/purchases')['balances'];assert {b['currency'] for b in balances}=={currency,c['currency']}
    assert next(b for b in balances if b['currency']==currency)['paid_minor']==567

def test_04_ui_created_archive_revoke(c):
    # Keep the UI long-title fixture until evidence capture; archive another own purchased fixture.
    cid=c['ids']['unflagged'];ok(c,'admin','delete','/admin/courses/'+cid);denied(c,'student','get','/courses/'+cid,404)
    assert cid not in [r['id'] for r in ok(c,'student','get','/my/library')['items']]

def test_05_original_settings_courses_invites_intact(c):
    original=json_util.loads(c['original_courses']);assert all(c['db'].courses.find_one({'id':row['id']})==row for row in original)
    assert json_util.dumps(list(c['db'].owner_invites.find({})),sort_keys=True)==c['original_invites']
    current=c['db'].settings.find_one({'id':'site'},{'_id':0});expected={**c['original']}
    if not expected['currency']:expected['currency']='USD'
    if not expected['payment_instructions'].strip():expected['payment_instructions']='TEST external transfer instructions'
    assert current==expected