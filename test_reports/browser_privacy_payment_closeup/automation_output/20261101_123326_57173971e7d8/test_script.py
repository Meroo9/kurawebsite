async def run_test(page, output_dir, page_url):
    from pathlib import Path
    import json, os,re
    from dotenv import load_dotenv
    load_dotenv('/app/frontend/.env')
    try:
        s=json.loads(Path('/app/test_reports/privacy_layout_state.json').read_text())
        base=os.environ['REACT_APP_BACKEND_URL'].rstrip('/')
        await page.set_viewport_size({'width':390,'height':844})
        await page.goto(base+'/login')
        await page.get_by_test_id('auth-email').fill(s['accounts']['owner']['email'])
        await page.get_by_test_id('auth-password').fill(s['password'])
        await page.get_by_test_id('auth-submit').click(force=True)
        await page.wait_for_url(re.compile('/dashboard$'),timeout=15000)
        await page.goto(base+'/dashboard/payments')
        await page.get_by_test_id('research-payments-tab').click(force=True)
        row=page.get_by_test_id('research-payment-row-'+s['rid'])
        await row.wait_for(timeout=15000)
        await row.scroll_into_view_if_needed()
        assert await row.locator('h2').inner_text()==s['title']
        assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        await page.screenshot(path='/app/test_reports/browser_privacy_payment_closeup/automation_output/20261101_123326_57173971e7d8/owner-payment-title-closeup-390.jpeg', type="jpeg", quality=40, full_page=False)
        print('PASS supplemental long-title payment screenshot: fully visible, no overflow')
        error_text=await page.evaluate("""() => {const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));return errorElements.map(el => el.textContent).join(', ');} """)
        if error_text: print('Found error message: '+error_text)
        else: print('No error messages found on the page')
    except Exception as e:
        print('FAIL supplemental payment screenshot',str(e))
