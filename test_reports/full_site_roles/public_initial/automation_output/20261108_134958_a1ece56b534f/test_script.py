async def run_test(page, output_dir, page_url):
    try:
        await page.set_viewport_size({'width':1920,'height':1080})
        await page.get_by_test_id('hero-title').wait_for(timeout=20000)
        await page.screenshot(path='/app/test_reports/full_site_roles/public_initial/automation_output/20261108_134958_a1ece56b534f/public-home-1920.jpeg', type="jpeg", quality=40, full_page=False)
        assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        print('PASS public home loaded without horizontal overflow')
    except Exception as e:
        print('FAIL public home:',str(e))
        raise
