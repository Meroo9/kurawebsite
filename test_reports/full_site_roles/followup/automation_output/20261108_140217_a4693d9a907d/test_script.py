async def run_test(page, output_dir, page_url):
    import sys,importlib
    sys.path.insert(0,'/app/tests')
    import full_site_roles_browser as suite
    suite=importlib.reload(suite)
    try:
        await suite.run_role_followup(page)
        print('ROLE FOLLOWUP RESULT:',sum(x['passed'] for x in suite.results),'/',len(suite.results))
        await page.set_viewport_size({'width':390,'height':844})
        await page.goto(suite.BASE+'/')
        await page.get_by_test_id('hero-title').wait_for()
        await suite.shot(page,'public-home-390')
    except Exception as e:
        print('FAIL role followup:',str(e))
        raise
