async def run_test(page, output_dir, page_url):
    try:
        await page.set_viewport_size({"width":1920,"height":1080})
        await page.get_by_test_id('posts-search').wait_for()
        await page.screenshot(path='/app/test_reports/browser_initial/automation_output/20261101_121348_50c8427ad1d6/kura-posts-initial.jpeg', type="jpeg", quality=40, full_page=False)
        print('PASS: posts loads and search is available')
        await page.get_by_test_id('nav-research').click()
        await page.get_by_test_id('research-sign-in').wait_for()
        print('PASS: research navigation is active')
        error_text = await page.evaluate("""() => {const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]')); return errorElements.map(el => el.textContent).join(", ");}""")
        print(f'Found error message: {error_text}' if error_text else 'No error messages found on the page')
    except Exception as e:
        print(f'FAIL: initial UI {e}')
