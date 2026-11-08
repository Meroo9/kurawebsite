async def run_test(page, output_dir, page_url):
    try:
        await page.set_viewport_size({'width':1920,'height':1080})
        await page.get_by_test_id('page-title').wait_for(timeout=15000)
        print('PASS initial public page:', await page.get_by_test_id('page-title').inner_text())
        await page.screenshot(path='/app/test_reports/browser_privacy_initial/automation_output/20261101_122502_05ea3c56e792/initial.jpeg', type="jpeg", quality=40, full_page=False)
    except Exception as e:
        print('FAIL initial load',str(e))
