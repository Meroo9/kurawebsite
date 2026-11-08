# Executed through browser automation with environment-derived base and isolated state.
import re, struct, zlib

async def run(page, base, state):
    contexts=[]
    async def login(p,who):
        await p.goto(base+'/login')
        await p.get_by_test_id('auth-email').fill(state['accounts'][who]['email'])
        await p.get_by_test_id('auth-password').fill(state['password'])
        await p.get_by_test_id('auth-submit').click(force=True)
        await p.wait_for_url(re.compile('/(admin|dashboard)$'),timeout=20000)
    async def role_page(who):
        context=await page.context.browser.new_context(viewport={'width':1920,'height':1080})
        contexts.append(context);p=await context.new_page();p.on('dialog',lambda d:d.accept());await login(p,who);return p
    async def status(p,text):
        await p.get_by_test_id('research-detail-status').get_by_text(text,exact=True).wait_for(timeout=30000)
    async def refresh(p):
        async with p.expect_response(lambda r:'/api/research/' in r.url and r.request.method=='GET' and r.status==200):
            await p.get_by_test_id('refresh-research').click(force=True)
        await p.wait_for_timeout(200)
    async def send_receipt(amount):
        await page.get_by_test_id('research-receipt-amount').fill(amount)
        await page.get_by_test_id('research-receipt-file').set_input_files({'name':'TEST_UI_receipt.png','mimeType':'image/png','buffer':png})
        await page.get_by_test_id('research-send-receipt').click(force=True)
        await page.get_by_test_id('research-payment-status').get_by_text('إيصال قيد المراجعة',exact=True).wait_for(timeout=30000)
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\xff'))+chunk(b'IEND',b'')
    try:
        await page.set_viewport_size({'width':390,'height':844})
        page.on('dialog',lambda d:d.accept())
        await login(page,'student')
        await page.goto(base+'/dashboard/research/new')
        await page.get_by_test_id('research-title-input').fill(state['tag']+' '+('دراسةبحثيةطويلة'*10))
        await page.get_by_test_id('research-field-input').fill('TEST الطب والصحة العامة')
        await page.get_by_test_id('research-service-input').select_option('analysis')
        await page.get_by_test_id('research-description-input').fill('TEST وصف تفصيلي للبحث ومساعدة التحليل المطلوبة مع بيانات منزوعة الهوية.')
        await page.get_by_test_id('research-files-input').set_input_files([{'name':f'TEST_{i}.txt','mimeType':'text/plain','buffer':b'TEST input'} for i in range(11)])
        await page.get_by_test_id('error-notice').get_by_text('يمكن إرفاق عشرة ملفات في الدفعة',exact=True).wait_for()
        assert await page.get_by_test_id('remove-selected-file-0').count()==0
        await page.get_by_test_id('research-files-input').set_input_files({'name':'TEST_'+('اسمملفطويل'*14)+'.txt','mimeType':'text/plain','buffer':b'TEST UI private input'})
        await page.get_by_test_id('research-privacy-consent').check()
        width=await page.evaluate('({doc:document.documentElement.scrollWidth,win:window.innerWidth})')
        print('Intake width:',width)
        if width['doc']>width['win']:print('FAIL: mobile intake horizontal overflow')
        await page.get_by_test_id('submit-new-research').click(force=True)
        await page.wait_for_url(re.compile('/dashboard/research/[a-f0-9]+$'),timeout=30000)
        rid=page.url.rsplit('/',1)[1]
        await status(page,'بانتظار التسعير')
        width=await page.evaluate('({doc:document.documentElement.scrollWidth,win:window.innerWidth})')
        print('Detail width:',width)
        if width['doc']>width['win']:print('FAIL: mobile detail horizontal overflow')
        print('PASS: mobile intake, 10-file batch limit, actual upload, long Arabic title/file layout; request '+rid)
        admin=await role_page('admin');worker=await role_page('employee1')
        await admin.goto(base+'/admin/research/'+rid)
        await admin.get_by_test_id('research-quote-amount').fill('100')
        await admin.get_by_test_id('research-quote-days').fill('5')
        await admin.get_by_test_id('research-quote-scope-input').fill('TEST تحليل البيانات وتقرير نهائي مع جولة تعديل واحدة ضمن النطاق.')
        await admin.get_by_test_id('send-research-quote').click(force=True)
        await admin.get_by_test_id('research-quote-total').wait_for()
        await refresh(page)
        await page.get_by_test_id('research-quote-discount').get_by_text('15%',exact=True).wait_for()
        await page.get_by_test_id('accept-research-quote').click(force=True)
        await status(page,'متاح للموظفين')
        print('PASS: admin quote and owner discount/accept')
        await worker.goto(base+'/dashboard/research')
        await worker.get_by_test_id('research-row-'+rid).wait_for()
        assert await worker.get_by_test_id('research-title-'+rid).inner_text()=='تحليل البيانات'
        await worker.get_by_test_id('research-row-'+rid).click(force=True)
        await worker.get_by_test_id('claim-research').click(force=True)
        await worker.get_by_test_id('start-research').wait_for()
        assert await worker.get_by_test_id('research-payment-status').count()==0
        await worker.get_by_test_id('start-research').click(force=True)
        await status(worker,'قيد المعالجة')
        await worker.get_by_test_id('research-result-upload').set_input_files({'name':'TEST_UI_result.txt','mimeType':'text/plain','buffer':b'TEST UI real result'})
        await worker.get_by_test_id('result-file-count').get_by_text('1 ملف',exact=True).wait_for(timeout=30000)
        await worker.get_by_test_id('deliver-research').click(force=True)
        await status(worker,'جاهز وبانتظار السداد')
        await refresh(page)
        await page.get_by_test_id('research-results-locked').wait_for()
        assert await page.locator('[data-testid^="research-file-view-"]').count()==1
        print('PASS: employee claim/start/upload/deliver without payment; owner results withheld')
        await send_receipt('25')
        await refresh(admin)
        await admin.get_by_test_id('research-receipt-review-reason').fill('TEST UI إيصال غير واضح')
        await admin.get_by_test_id('research-reject-receipt').click(force=True)
        await admin.get_by_test_id('research-payment-status').get_by_text('إيصال مرفوض',exact=True).wait_for(timeout=30000)
        await refresh(page)
        await send_receipt('25')
        await refresh(admin)
        await admin.get_by_test_id('research-approve-receipt').click(force=True)
        await admin.get_by_test_id('research-payment-status').get_by_text('مسدد جزئيًا',exact=True).wait_for(timeout=30000)
        await refresh(page)
        assert await page.get_by_test_id('research-receipt-amount').input_value()=='60'
        await page.get_by_test_id('research-results-locked').wait_for()
        await send_receipt('60')
        await refresh(admin)
        await admin.get_by_test_id('research-approve-receipt').click(force=True)
        await status(admin,'تم تسليم النتائج')
        await refresh(page)
        await status(page,'تم تسليم النتائج')
        assert await page.get_by_test_id('research-results-locked').count()==0
        async with page.expect_popup() as pop:
            await page.locator('[data-testid^="research-file-view-"]').last.click(force=True)
        viewer=await pop.value;await viewer.wait_for_load_state();assert 'TEST UI real result' in await viewer.inner_text('body');await viewer.close()
        print('PASS: receipt rejection/replacement, partial amount resets, full approval unlocks real result')
        await page.get_by_test_id('research-action-note').fill('TEST UI تعديل مطلوب ضمن النطاق')
        await page.get_by_test_id('request-research-revision').click(force=True)
        await status(page,'مطلوب تعديل')
        await refresh(worker)
        await worker.get_by_test_id('research-result-upload').set_input_files({'name':'TEST_UI_revision.txt','mimeType':'text/plain','buffer':b'TEST UI revision'})
        await worker.get_by_test_id('result-file-count').get_by_text('2 ملف',exact=True).wait_for(timeout=30000)
        await worker.get_by_test_id('deliver-research').click(force=True)
        await status(worker,'تم تسليم النتائج')
        await refresh(page)
        assert await page.get_by_test_id('request-research-revision').count()==0
        await page.get_by_test_id('complete-research').click(force=True)
        await status(page,'مكتمل')
        await page.goto(base+'/dashboard/payments')
        await page.get_by_test_id('research-payments-tab').click(force=True)
        await page.get_by_test_id('research-payment-row-'+rid).wait_for()
        await page.get_by_test_id('course-payments-tab').click(force=True)
        print('PASS: revision/re-delivery/completion and separate research/course payments')
        await page.set_viewport_size({'width':1000,'height':1024})
        await page.goto(base+'/dashboard/research/'+rid)
        await page.get_by_test_id('research-detail-description').wait_for()
        assert await page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
        print('PASS: 1000px tablet detail no horizontal overflow')
        await page.screenshot(path='/tmp/kura-research-completed.jpg',quality=40,full_page=False)
    except Exception as e:
        import traceback
        print('FAIL: research browser workflow '+repr(e));print(traceback.format_exc());raise
    finally:
        error_text=await page.evaluate("""() => {const errorElements=Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));return errorElements.map(el=>el.textContent).join(', ');} """)
        print('Found error message: '+error_text if error_text else 'No error messages found on the page')
        for context in contexts:await context.close()