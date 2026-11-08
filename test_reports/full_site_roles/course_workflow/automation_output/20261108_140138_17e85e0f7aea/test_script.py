async def run_test(page, output_dir, page_url):
    import sys,importlib
    sys.path.insert(0,'/app/tests')
    import full_site_roles_browser as suite
    suite=importlib.reload(suite)
    try:
        c=suite.load()
        c['accounts']['ui_pending']=dict(c['accounts']['pending'])
        c['cookies']['ui_pending']=dict(c['cookies']['pending'])
        suite.save(c)
        await suite.run_accounts_courses(page,students=())
        print('COURSE WORKFLOW RESULT:',sum(x['passed'] for x in suite.results),'/',len(suite.results))
    except Exception as e:
        print('FAIL course workflow:',str(e))
        raise
