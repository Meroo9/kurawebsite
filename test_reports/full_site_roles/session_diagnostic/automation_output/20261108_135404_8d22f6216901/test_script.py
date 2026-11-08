async def run_test(page, output_dir, page_url):
    import sys,importlib
    sys.path.insert(0,'/app/tests')
    import full_site_roles_browser as suite
    suite=importlib.reload(suite)
    try:
        ctx,p=await suite.context_for(page,suite.load(),'visitor')
        for route in ['/dashboard','/admin','/admin/users','/admin/research','/admin/posts','/admin/settings']:
            await p.goto(suite.BASE+route)
            await p.wait_for_timeout(600)
            r=await p.request.get(suite.BASE+'/api/auth/me')
            attrs=[{k:v for k,v in x.items() if k not in ['value']} for x in await ctx.cookies()]
            print('CHECK',route,'finalpath',p.url.split(suite.BASE)[-1],'me',r.status,'cookie_attrs',attrs)
        await ctx.close()
        print('PASS session diagnostic complete')
    except Exception as e:
        print('FAIL session diagnostic:',str(e))
        raise
