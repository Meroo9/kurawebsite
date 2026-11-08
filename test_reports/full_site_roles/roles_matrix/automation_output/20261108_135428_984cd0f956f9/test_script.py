async def run_test(page, output_dir, page_url):
    import sys,importlib
    sys.path.insert(0,'/app/tests')
    import full_site_roles_browser as suite
    suite=importlib.reload(suite)
    try:
        await suite.run_roles(page)
        print('ROLES RESULT:',sum(x['passed'] for x in suite.results),'/',len(suite.results))
    except Exception as e:
        print('FAIL role matrix:',str(e))
        raise
