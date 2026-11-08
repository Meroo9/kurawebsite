async def run_test(page, output_dir, page_url):
    try:
        import json
        from pathlib import Path
        from dotenv import dotenv_values
        s=json.loads(Path('/app/test_reports/research_test_state.json').read_text());base=dotenv_values('/app/frontend/.env')['REACT_APP_BACKEND_URL'].rstrip('/')
        await page.set_viewport_size({'width':390,'height':844})
        await page.get_by_test_id('auth-email').fill(s['accounts']['student']['email'])
        await page.get_by_test_id('auth-password').fill(s['password'])
        await page.get_by_test_id('auth-submit').click(force=True)
        await page.wait_for_url('**/dashboard')
        await page.goto(base+'/dashboard/research/6715a6301c77e53b7e6d81b5')
        await page.get_by_test_id('research-detail-description').wait_for()
        for width,height in [(390,844),(1000,1024),(1920,1080)]:
            await page.set_viewport_size({'width':width,'height':height})
            overflow=await page.evaluate("""() => ({doc:document.documentElement.scrollWidth,win:innerWidth, elements:[...document.querySelectorAll('h1,.page-heading,.workspace-content,.workspace-body')].map(e=>({tag:e.tagName,cls:e.className,w:e.getBoundingClientRect().width,scroll:e.scrollWidth,wrap:getComputedStyle(e).overflowWrap,min:getComputedStyle(e).minWidth}))})""")
            print('Layout diagnostic',overflow)
            await page.screenshot(path=f"/app/test_reports/browser_layout/automation_output/20261101_121752_030d4f14e0e1/kura-overflow-{width}.jpeg", type="jpeg", quality=40, full_page=False)
        error_text=await page.evaluate("""() => {const errorElements=Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]'));return errorElements.map(el=>el.textContent).join(', ');} """)
        print('Found error message: '+error_text if error_text else 'No error messages found on the page')
    except Exception as e:
        print('FAIL layout diagnostic:',repr(e))
