async def run_test(page, output_dir, page_url):
    import sys,importlib
    sys.path.insert(0,'/app/tests')
    import full_site_roles_browser as suite
    suite=importlib.reload(suite)
    import full_site_workflow_adapters as adapter
    adapter=importlib.reload(adapter)
    try:
        await adapter.run_existing(page,'research')
        print('RESEARCH WORKFLOW RESULT:',sum(x['passed'] for x in suite.results),'/',len(suite.results))
    except Exception as e:
        print('FAIL research workflow:',str(e))
        raise
