# Actual posts CRUD/moderation plus failed research intake recovery and cancellation UI.
import re,struct,zlib

async def run(page,base,state):
    contexts=[]
    async def login(p,who):
        await p.goto(base+'/login');await p.get_by_test_id('auth-email').fill(state['accounts'][who]['email']);await p.get_by_test_id('auth-password').fill(state['password']);await p.get_by_test_id('auth-submit').click(force=True);await p.wait_for_url(re.compile('/(admin|dashboard)$'),timeout=20000)
    async def other(who):
        ctx=await page.context.browser.new_context(viewport={'width':1920,'height':1080});contexts.append(ctx);p=await ctx.new_page();p.on('dialog',lambda d:d.accept());await login(p,who);return p
    async def refresh(p):
        async with p.expect_response(lambda r:'/api/research/' in r.url and r.request.method=='GET' and r.status==200):await p.get_by_test_id('refresh-research').click(force=True)
        await p.wait_for_timeout(200)
    async def quote(admin):
        await admin.get_by_test_id('research-quote-amount').fill('50');await admin.get_by_test_id('research-quote-scope-input').fill('TEST نطاق تحليل البيانات والنتائج المتفق عليه');await admin.get_by_test_id('send-research-quote').click(force=True);await admin.get_by_test_id('research-quote-total').wait_for()
    def chunk(k,d):return struct.pack('>I',len(d))+k+d+struct.pack('>I',zlib.crc32(k+d)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\xff'))+chunk(b'IEND',b'')
    try:
        await page.set_viewport_size({'width':1920,'height':1080});page.on('dialog',lambda d:d.accept());await login(page,'student');admin=await other('admin')
        await admin.goto(base+'/admin/posts');await admin.get_by_test_id('create-post').click(force=True)
        await admin.get_by_test_id('post-title-input').fill(state['tag']+' UI منشور علمي للاختبار')
        await admin.get_by_test_id('post-body-input').fill('TEST محتوى علمي فعلي من الواجهة. <script>window.TEST_XSS=1</script>')
        await admin.get_by_test_id('post-image-input').set_input_files({'name':'TEST_UI_post.png','mimeType':'image/png','buffer':png})
        async with admin.expect_response(lambda r:r.url.endswith('/api/admin/posts') and r.request.method=='POST') as created:await admin.get_by_test_id('save-post').click(force=True)
        post=await (await created.value).json();pid=post['id'];fid=post['image_id']
        await admin.get_by_test_id('post-editor').wait_for(state='hidden')
        await admin.get_by_test_id('admin-post-'+pid).wait_for()
        print('PASS: admin actual post/image create')
        await page.goto(base+'/posts');await page.get_by_test_id('posts-search').fill(state['tag']+' UI');await page.get_by_test_id('post-title-link-'+pid).click(force=True)
        await page.get_by_test_id('post-image-'+pid).wait_for();await page.wait_for_function("id=>document.querySelector('[data-testid=\"post-image-'+id+'\"]').naturalWidth>0",arg=pid)
        assert await page.evaluate('window.TEST_XSS===undefined')
        await page.get_by_test_id('post-like-'+pid).click(force=True);await page.get_by_test_id('post-like-count-'+pid).get_by_text('1',exact=True).wait_for()
        await page.reload();await page.get_by_test_id('post-like-'+pid).wait_for();assert await page.get_by_test_id('post-like-'+pid).get_attribute('aria-pressed')=='true'
        await page.get_by_test_id('comment-body').fill('<img src=x onerror="window.TEST_XSS=2"> TEST تعليق آمن')
        async with page.expect_response(lambda r:r.url.endswith('/comments') and r.request.method=='POST') as added:await page.get_by_test_id('submit-comment').click(force=True)
        comment=await (await added.value).json();cid=comment['id'];await page.get_by_test_id('comment-body-'+cid).wait_for();assert await page.get_by_test_id('comment-body-'+cid).inner_text()==comment['body'];assert await page.evaluate('window.TEST_XSS===undefined')
        for width,height in [(390,844),(1000,1024)]:
            await page.set_viewport_size({'width':width,'height':height});assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth');print('PASS: post detail layout',width)
        await page.screenshot(path='/tmp/kura-post-mobile.jpg',quality=40,full_page=False)
        print('PASS: feed/detail real image, persistent like, comment, plain-text XSS')
        await admin.goto(base+'/posts/'+pid);await admin.get_by_test_id('delete-comment-'+cid).click(force=True);await admin.get_by_test_id('comment-'+cid).wait_for(state='hidden')
        await admin.goto(base+'/admin/posts');await admin.get_by_test_id('edit-post-'+pid).click(force=True);await admin.get_by_test_id('post-title-input').fill(state['tag']+' UI عنوان معدل');await admin.get_by_test_id('remove-post-image').click();await admin.get_by_test_id('remove-post-image').wait_for(state='hidden');await admin.get_by_test_id('save-post').click(force=True);await admin.get_by_test_id('post-editor').wait_for(state='hidden')
        await page.reload();await page.get_by_test_id('post-title-'+pid).get_by_text(state['tag']+' UI عنوان معدل',exact=True).wait_for();assert await page.get_by_test_id('post-image-'+pid).count()==0
        assert (await page.request.get(base+'/api/post-images/'+fid)).status==404
        await admin.get_by_test_id('edit-post-'+pid).click(force=True);await admin.get_by_test_id('post-published-input').uncheck(force=True);await admin.get_by_test_id('save-post').click(force=True);await admin.get_by_test_id('post-editor').wait_for(state='hidden')
        assert (await page.request.get(base+'/api/posts/'+pid)).status==404
        await admin.get_by_test_id('delete-post-'+pid).click(force=True);await admin.get_by_test_id('admin-post-'+pid).wait_for(state='hidden')
        print('PASS: moderation, text edit, image removal revokes public image, draft hides and delete')
        await page.set_viewport_size({'width':390,'height':844});await page.goto(base+'/dashboard/research/new')
        await page.get_by_test_id('research-title-input').fill(state['tag']+' UI مسودة للاستعادة');await page.get_by_test_id('research-field-input').fill('TEST طب');await page.get_by_test_id('research-description-input').fill('TEST وصف مطول لاختبار استعادة المسودة بعد خطأ رفع الملف')
        await page.get_by_test_id('research-files-input').set_input_files({'name':'TEST_invalid.mp4','mimeType':'video/mp4','buffer':b'0000ftyp'})
        await page.get_by_test_id('research-privacy-consent').check();await page.get_by_test_id('submit-new-research').click(force=True);await page.get_by_test_id('resume-research-draft').wait_for(timeout=30000)
        await page.get_by_test_id('resume-research-draft').click(force=True);await page.get_by_test_id('research-detail-status').get_by_text('مسودة',exact=True).wait_for();rid=page.url.rsplit('/',1)[1]
        await page.get_by_test_id('edit-research-details').click(force=True);await page.get_by_test_id('edit-research-title').fill(state['tag']+' UI تفاصيل معدلة');await page.get_by_test_id('save-research-details').click(force=True);await page.get_by_test_id('edit-research-title').wait_for(state='hidden')
        await page.get_by_test_id('research-input-upload').set_input_files({'name':'TEST_resume.txt','mimeType':'text/plain','buffer':b'TEST resumed draft'})
        await page.get_by_test_id('input-file-count').get_by_text('1 ملف',exact=True).wait_for(timeout=30000)
        await page.get_by_test_id('submit-research-draft').click(force=True);await page.get_by_test_id('research-detail-status').get_by_text('بانتظار التسعير',exact=True).wait_for()
        print('PASS: invalid upload retains draft; resume/edit/upload/submit succeeds')
        await admin.goto(base+'/admin/research/'+rid);await quote(admin);await refresh(page)
        await page.get_by_test_id('reject-research-quote-reason').fill('TEST UI يرجى توضيح النطاق');await page.get_by_test_id('reject-research-quote').click(force=True);await page.get_by_test_id('research-quote-history').wait_for()
        await refresh(admin);await quote(admin);await refresh(page);await page.get_by_test_id('accept-research-quote').click(force=True);await page.get_by_test_id('research-detail-status').get_by_text('متاح للموظفين',exact=True).wait_for()
        worker=await other('employee1');await worker.goto(base+'/dashboard/research/'+rid);await worker.get_by_test_id('claim-research').click(force=True);await worker.get_by_test_id('start-research').wait_for()
        await refresh(page);await page.get_by_test_id('research-cancel-reason').fill('TEST UI إلغاء بعد الاستلام');await page.get_by_test_id('cancel-research').click(force=True);await page.get_by_test_id('cancel-request-notice').wait_for()
        await admin.get_by_test_id('refresh-research').click(force=True);await admin.get_by_test_id('research-action-note').fill('TEST UI رفض الإلغاء لحين تنسيق التسوية');await admin.get_by_test_id('reject-research-cancel').click(force=True);await admin.get_by_test_id('cancel-request-notice').wait_for(state='hidden')
        await refresh(page);await page.get_by_test_id('research-cancel-reason').fill('TEST UI تأكيد الإلغاء');await page.get_by_test_id('cancel-research').click(force=True);await page.get_by_test_id('cancel-request-notice').wait_for()
        await refresh(admin);await admin.get_by_test_id('research-action-note').fill('TEST UI الموافقة؛ لا مدفوعات أو استرداد مطلوب');await admin.get_by_test_id('approve-research-cancel').click(force=True);await admin.get_by_test_id('research-detail-status').get_by_text('ملغى',exact=True).wait_for()
        await refresh(page);await page.get_by_test_id('cancelled-input-files').wait_for();await page.get_by_test_id('cancellation-resolution').wait_for()
        print('PASS: quote rejection/history, requote, owner cancel request, admin reasoned reject/approve settlement UI')
    except Exception as e:
        import traceback
        print('FAIL: posts/recovery browser '+repr(e));print(traceback.format_exc());raise
    finally:
        error_text=await page.evaluate("""() => {const errorElements=Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));return errorElements.map(el=>el.textContent).join(', ');} """)
        print('Found error message: '+error_text if error_text else 'No error messages found on the page')
        for ctx in contexts:await ctx.close()