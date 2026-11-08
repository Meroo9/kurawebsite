async def run_test(page, output_dir, page_url):
    try:
        await page.set_viewport_size({'width':1920,'height':1080})
        await page.get_by_test_id('hero-title').wait_for(timeout=20000)
        await page.screenshot(path='/app/test_reports/full_site_roles/fixes/initial/automation_output/20261108_140843_76c01d3fbb77/initial.jpeg', type="jpeg", quality=40, full_page=False)
        print('PASS frontend initial load')
    except Exception as e:
        print('FAIL frontend initial load',str(e))
