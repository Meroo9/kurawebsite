# Current iteration targeted archive/audit, access guards, real MP4 storage and preservation tests.
import pytest
from bson import json_util
from full_fix_support import load, ok, req
@pytest.fixture(scope='module')
def c():return load()
def test_01_health_and_long_title(c):
    assert ok(c,None,'get','/health')['status']=='ok'
    row=ok(c,None,'get','/courses/'+c['ids']['long']);assert row['title']==c['title'] and not row['has_access']
def test_02_missing_course_no_audit(c):
    target=c['tag']+'_MISSING_COURSE';r=req(c,'admin','delete','/admin/courses/'+target)
    assert r.status_code==404 and 'الكورس' in r.json()['detail']
    assert c['db'].audit.count_documents({'target':target})==0
def test_03_missing_lecture_no_audit(c):
    target=c['tag']+'_MISSING_LECTURE';r=req(c,'admin','delete','/admin/lectures/'+target)
    assert r.status_code==404 and 'المحاضرة' in r.json()['detail']
    assert c['db'].audit.count_documents({'target':target})==0
def test_04_archive_course_once(c):
    target=c['ids']['archive_course'];assert ok(c,'admin','delete','/admin/courses/'+target)=={'success':True}
    assert req(c,None,'get','/courses/'+target).status_code==404
    r=req(c,'admin','delete','/admin/courses/'+target);assert r.status_code==404 and 'الكورس' in r.json()['detail']
    assert c['db'].audit.count_documents({'target':target,'action':'course_archived'})==1
def test_05_archive_lecture_once(c):
    target=c['ids']['archive_lid'];assert ok(c,'admin','delete','/admin/lectures/'+target)=={'success':True}
    assert ok(c,'admin','get','/courses/'+c['ids']['archive_lecture'])['lectures']==[]
    r=req(c,'admin','delete','/admin/lectures/'+target);assert r.status_code==404 and 'المحاضرة' in r.json()['detail']
    assert c['db'].audit.count_documents({'target':target,'action':'lecture_archived'})==1
def test_06_existing_access_unchanged(c):
    assert ok(c,'visitor','get','/my/purchases/course/'+c['ids']['long'])['purchase']['status']=='approved'
    assert ok(c,'visitor','get','/courses/'+c['ids']['long'])['has_access']
    assert ok(c,'student','get','/courses/'+c['ids']['normal'])['has_access']
    assert not ok(c,'visitor','get','/courses/'+c['ids']['normal'])['has_access']
def test_07_real_mp4_metadata_range_and_permission(c):
    fid=c['ids']['video_file'];m=ok(c,'student','get','/files/'+fid+'/metadata');assert m['content_type']=='video/mp4' and m['size']==c['video_size']
    r=req(c,'student','get','/files/'+fid,headers={'Range':'bytes=0-31'});assert r.status_code==206 and r.content[4:8]==b'ftyp' and len(r.content)==32
    for who,code in [(None,401),('visitor',403)]:
        for path in ['/files/'+fid,'/files/'+fid+'/metadata']:
            r=req(c,who,'get',path);assert r.status_code==code and r.json()['detail']
def test_08_originals_preserved(c):
    for key in ['settings','owner_invites']:assert json_util.dumps(list(c['db'][key].find({})),sort_keys=True)==c['original'][key]
    original=json_util.loads(c['original']['courses']);assert all(c['db'].courses.find_one({'_id':r['_id']})==r for r in original)