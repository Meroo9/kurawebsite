async def run_test(page, output_dir, page_url):
    import sys,importlib
    sys.path.insert(0,'/app/tests')
    import full_site_fixes_browser
    f=importlib.reload(full_site_fixes_browser)
    c=f.load()
    for role,width in [('ui_pending_typed',1920),('ui_pending_calendar',390)]:
        ctx,p=await f.context(page,c,role,width)
        try:
            await p.goto(f.BASE+'/dashboard/profile')
            avatar=p.get_by_test_id('profile-avatar')
            await avatar.wait_for()
            await p.wait_for_function("()=>{const i=document.querySelector('[data-testid=profile-avatar]');return i && i.complete && i.naturalWidth>0}")
            await avatar.scroll_into_view_if_needed()
            await f.shot(p,f'{role}-avatar-profile-{width}')
            f.record(f'{role} real persisted avatar renders @{width}')
        except Exception as e:
            f.record(f'{role} avatar renders @{width}',False,repr(e))
        finally:
            await ctx.close()
    for width in (390,1920):
        ctx,p=await f.context(page,c,'student',width)
        try:
            await p.goto(f.BASE+'/courses/'+c['ids']['normal'])
            await p.get_by_test_id('view-lecture-'+c['ids']['video_lecture']).click()
            video=p.get_by_test_id('lecture-video')
            await video.wait_for()
            await p.wait_for_function("()=>{const v=document.querySelector('[data-testid=lecture-video]');return v && Number.isFinite(v.duration) && v.readyState>=2}",timeout=30000)
            await video.evaluate('v=>{v.currentTime=5}')
            await p.wait_for_function("()=>!document.querySelector('[data-testid=lecture-video]').seeking",timeout=15000)
            await video.scroll_into_view_if_needed()
            await f.shot(p,f'student-video-play-seek-{width}')
            print('PASS improved video screenshot',width)
        except Exception as e:
            print('FAIL video evidence',width,repr(e))
        finally:
            await ctx.close()
    f.report('avatar_supplement_browser')
