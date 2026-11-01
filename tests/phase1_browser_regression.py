# Browser regression exercised through public-origin Playwright: run after API setup, before cleanup.
import re,secrets,struct,zlib

async def run(page, base, state):
    """Supply BASE from frontend .env and isolated state from test_state.json; no owner activation."""
    tag=state['tag'];password=state['password'];ids=state['ids']
    async def login(who):
        await page.goto(base+'/login')
        await page.get_by_test_id('auth-email').fill(state['accounts'][who]['email'])
        await page.get_by_test_id('auth-password').fill(password)
        await page.get_by_test_id('auth-submit').click(force=True)
        await page.wait_for_url(re.compile('/(admin|dashboard)$'),timeout=15000)
        await page.goto(base+('/admin' if who=='admin' else '/dashboard'))
    async def logout():
        await page.goto(base+'/dashboard')
        await page.get_by_test_id('logout').click(force=True)
        await page.get_by_test_id('auth-email').wait_for()
    def chunk(kind,data):
        return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\xff'))+chunk(b'IEND',b'')
    try:
        await page.set_viewport_size({'width':390,'height':844})
        for student in [False,True]:
            await page.goto(base+'/register')
            suffix=secrets.token_hex(4);email=tag.lower()+'ui'+suffix+'@example.com'
            await page.get_by_test_id('register-name').fill(tag+' UI '+suffix)
            await page.get_by_test_id('auth-email').fill(email)
            await page.get_by_test_id('register-phone').fill('+1778'+str(secrets.randbelow(9000000)+1000000))
            await page.get_by_test_id('auth-password').fill(password)
            if student:
                await page.get_by_test_id('register-is-student').check(force=True)
                await page.get_by_test_id('register-university').fill('TEST university')
                await page.get_by_test_id('register-field').fill('TEST medicine')
                await page.get_by_test_id('register-krc').fill('KRC'+suffix.upper())
                date=page.get_by_test_id('register-date')
                assert await date.get_attribute('type')=='text'
                await date.fill('2025-01-10')
                await page.get_by_test_id('register-date-calendar-button').click(force=True)
                await page.wait_for_timeout(200)
                await page.get_by_test_id('register-date-calendar').locator('button').filter(has_text=re.compile('^15$')).click(force=True)
                assert await date.input_value()=='2025-01-15'
            await page.get_by_test_id('auth-submit').click(force=True)
            await page.wait_for_url('**/dashboard',timeout=20000)
            me=await page.evaluate("async()=> (await fetch('/api/auth/me')).json()")
            assert me['email']==email and me['role']=='visitor'
            assert me['student_status']==('pending' if student else 'none')
            assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            print('PASS actual registration:',student)
            await logout()
        await page.set_viewport_size({'width':1920,'height':1080})
        await login('admin')
        await page.get_by_test_id('workspace-users').click(force=True)
        await page.get_by_test_id('users-search').fill(state['accounts']['pending']['email'])
        await page.get_by_test_id('edit-user-'+state['accounts']['pending']['id']).click(force=True)
        corrected='KRC'+secrets.token_hex(8).upper()
        await page.get_by_test_id('admin-krc-input').fill(corrected)
        await page.get_by_test_id('save-krc-correction').click(force=True)
        await page.get_by_test_id('user-editor').wait_for(state='hidden')
        await page.get_by_test_id('user-row-'+state['accounts']['pending']['id']).get_by_text(corrected,exact=True).wait_for()
        print('PASS KRC correction')
        await logout();await login('pending')
        await page.goto(base+'/dashboard/profile')
        assert await page.get_by_test_id('profile-krc').is_disabled()
        assert await page.get_by_test_id('profile-krc').input_value()==corrected
        await logout();await login('other')
        pid=ids['other_purchase'];cid=ids['course']
        await page.goto(base+'/courses/'+cid)
        await page.get_by_test_id('receipt-file-'+pid).wait_for()
        assert await page.get_by_test_id('course-purchase').count()==0
        print('PASS exact purchase beyond history page')
        for decision in ['rejected','approved']:
            await page.get_by_test_id('receipt-file-'+pid).set_input_files({'name':'TEST_receipt.png','mimeType':'image/png','buffer':png})
            await page.get_by_test_id('receipt-submit-'+pid).click(force=True)
            await page.get_by_test_id('purchase-status').get_by_text('قيد المراجعة',exact=True).wait_for(timeout=30000)
            await logout();await login('admin')
            await page.get_by_test_id('workspace-purchases').click(force=True)
            await page.get_by_test_id('review-purchase-'+pid).click(force=True)
            if decision=='rejected':
                await page.get_by_test_id('receipt-rejection-reason').fill('TEST UI unreadable receipt')
                await page.get_by_test_id('reject-receipt').click(force=True)
            else:
                page.once('dialog',lambda dialog:dialog.accept())
                await page.get_by_test_id('approve-receipt').click(force=True)
            await page.get_by_test_id('receipt-review-modal').wait_for(state='hidden')
            await logout();await login('other');await page.goto(base+'/courses/'+cid)
            print('PASS receipt review:',decision)
        await page.get_by_test_id('course-access-granted').wait_for()
        responses=[]
        page.on('response',lambda r:responses.append((r.url,r.status)) if '/files/'+ids['lecture_file'] in r.url else None)
        await page.get_by_test_id('view-lecture-'+ids['lecture']).click(force=True)
        await page.get_by_test_id('lecture-document').wait_for(timeout=20000)
        assert any('/metadata' in url and code==200 for url,code in responses)
        assert any(url.endswith('/'+ids['lecture_file']) and code==200 for url,code in responses)
        print('PASS private viewer')
        await logout();await login('visitor')
        await page.get_by_test_id('my-course-count').get_by_text('15',exact=True).wait_for()
        await page.get_by_test_id('workspace-courses').click(force=True)
        await page.get_by_test_id('pagination-status').get_by_text('1 / 2',exact=True).wait_for()
        assert await page.locator('a.course-card').count()==12
        await page.get_by_test_id('next-page').click(force=True)
        await page.get_by_test_id('pagination-status').get_by_text('2 / 2',exact=True).wait_for()
        await page.wait_for_timeout(400)
        assert await page.locator('a.course-card').count()==3
        await page.get_by_test_id('my-courses-search').fill(tag+' Library 13')
        await page.wait_for_timeout(500)
        assert await page.locator('a.course-card').count()==1
        await page.get_by_test_id('my-courses-category').select_option('medical')
        await page.get_by_test_id('empty-state').wait_for()
        await page.get_by_test_id('my-courses-category').select_option(ids['category'])
        await page.wait_for_timeout(400)
        assert await page.locator('a.course-card').count()==1
        await page.set_viewport_size({'width':390,'height':844})
        assert await page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
        print('PASS library pagination/filter/mobile')
    except Exception as exc:
        print('FAIL browser regression:',str(exc))
        raise
    finally:
        error_text=await page.evaluate("""() => {const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]')); return errorElements.map(el => el.textContent).join(', ');} """)
        print('Found error message: '+error_text if error_text else 'No error messages found on the page')