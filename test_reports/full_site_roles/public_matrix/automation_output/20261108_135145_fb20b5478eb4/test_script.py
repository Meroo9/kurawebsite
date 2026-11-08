async def run_test(page, output_dir, page_url):
    import sys
    sys.path.insert(0,'/app/tests')
    import full_site_roles_browser as suite
    try:
        await suite.run_public(page)
        print('PUBLIC RESULT:',sum(x['passed'] for x in suite.results),'/',len(suite.results))
    except Exception as e:
        print('FAIL public suite:',str(e))
        raise
