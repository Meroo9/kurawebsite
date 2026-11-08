async def run_test(page, output_dir, page_url):
    import sys,importlib
    sys.path.insert(0,'/app/tests')
    import full_site_fixes_browser
    f=importlib.reload(full_site_fixes_browser)
    c=f.load()
    for role,width in [('ui_pending_typed',1920),('ui_pending_calendar',390)]:
        ctx,p=await f.context(page,c,role,width,cookie=False)
        try:
            await f.login(p,c,role)
            c['cookies'][role]={'kura_session':next(x['value'] for x in await ctx.cookies() if x['name']=='kura_session')}
            f.save(c)
            await p.goto(f.BASE+'/dashboard/profile')
            avatar=p.get_by_test_id('profile-avatar')
            await avatar.wait_for()
            await p.wait_for_function("()=>{const i=document.querySelector('[data-testid=profile-avatar]');return i && i.complete && i.naturalWidth>0}")
            state=await f.me(p)
            assert state['role']=='student' and state['student_status']=='approved' and state['avatar_id']
            await avatar.scroll_into_view_if_needed()
            await f.shot(p,f'{role}-avatar-profile-{width}')
            f.record(f'{role} real persisted avatar renders @{width}')
        except Exception as e:
            await f.errors(p)
            f.record(f'{role} real persisted avatar renders @{width}',False,repr(e))
        finally:
            await ctx.close()
    f.report('avatar_verified_browser')
