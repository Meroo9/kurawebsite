async def run_test(page, output_dir, page_url):
    import sys,importlib
    sys.path.insert(0,'/app/tests')
    import full_site_roles_browser as suite
    suite=importlib.reload(suite)
    try:
        ctx,p=await suite.context_for(page,suite.load(),'ui_visitor')
        await p.set_viewport_size({'width':390,'height':844})
        await p.goto(suite.BASE+'/dashboard/profile')
        await p.get_by_test_id('profile-full-name').fill(suite.load()['accounts']['ui_visitor']['name']+' diagnostic')
        await p.get_by_test_id('save-profile').click(force=True)
        await p.get_by_test_id('profile-name').get_by_text(suite.load()['accounts']['ui_visitor']['name']+' diagnostic',exact=True).wait_for()
        print('LOGOUT HIT TEST:',await p.get_by_test_id('logout').evaluate('(e)=>{const r=e.getBoundingClientRect();const hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return {visible:e.checkVisibility(),rect:{x:r.x,y:r.y,width:r.width,height:r.height},hitTag:hit?.tagName,hitTest:hit?.getAttribute("data-testid"),hitToast:!!hit?.closest("[data-sonner-toast]")}}'))
        await suite.shot(p,'mobile-logout-toast-diagnostic')
        await p.wait_for_timeout(5000)
        async with p.expect_response(lambda r:r.url.endswith('/api/auth/logout')) as out:
            await p.get_by_test_id('logout').click(force=True)
        print('LOGOUT response',(await out.value).status)
        await p.wait_for_url('**/login',timeout=10000)
        print('PASS logout after notification disappears')
        await ctx.close()
    except Exception as e:
        print('FAIL logout diagnostic:',str(e))
        raise
