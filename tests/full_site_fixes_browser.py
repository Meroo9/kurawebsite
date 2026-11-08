# Actual browser regression for fixed layouts/selectors, pending signup, employee lifecycle and video.
import json,re,secrets,struct,zlib
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path('/app/test_reports/full_site_roles/fixes')
BASE=next(x.split('=',1)[1].strip() for x in Path('/app/frontend/.env').read_text().splitlines() if x.startswith('REACT_APP_BACKEND_URL=')).rstrip('/')
def load():return json.loads((ROOT/'private_state.json').read_text())
def save(c):(ROOT/'private_state.json').write_text(json.dumps(c))
checks=[];screens=[]
def record(name,passed=True,error=''):
    checks.append({'check':name,'passed':passed,'error':str(error)});print(('PASS ' if passed else 'FAIL ')+name+(' '+str(error) if error else ''))
def report(name):(ROOT/(name+'.json')).write_text(json.dumps({'checks':checks,'screenshots':screens},ensure_ascii=False,indent=2))
async def shot(p,name):
    await p.wait_for_timeout(250);path=ROOT/(name+'.jpg');await p.screenshot(path=str(path),quality=40,full_page=False);screens.append(str(path))
async def settled(p):
    await p.wait_for_timeout(250);await p.get_by_test_id('loading-state').first.wait_for(state='hidden',timeout=20000)
async def errors(p):
    error_text=await p.evaluate('''() => { const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]')); return errorElements.map(el => el.textContent).join(', '); }''')
    print('Found error message: '+error_text if error_text else 'No error messages found on the page');return error_text
async def context(page,c,role,width=1920,cookie=True):
    ctx=await page.context.browser.new_context(viewport={'width':width,'height':844 if width==390 else 1080})
    if cookie:await ctx.add_cookies([{'name':'kura_session','value':c['cookies'][role]['kura_session'],'domain':urlparse(BASE).hostname,'path':'/api','secure':True,'httpOnly':True,'sameSite':'Lax'}])
    return ctx,await ctx.new_page()
async def login(p,c,role):
    await p.goto(BASE+'/login');await p.get_by_test_id('auth-email').fill(c['accounts'][role]['email']);await p.get_by_test_id('auth-password').fill(c['password']);await p.get_by_test_id('auth-submit').click();await p.wait_for_url(re.compile('/(dashboard|admin)$'),timeout=20000)
async def me(p):return await p.evaluate("async()=> (await fetch('/api/auth/me')).json()")
async def width_ok(p):assert await p.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Document overflows'
async def text_ok(locator,expected):
    assert await locator.inner_text()==expected
    d=await locator.evaluate('''el=>{const s=getComputedStyle(el),r=el.getBoundingClientRect();return {scroll:el.scrollWidth,client:el.clientWidth,sh:el.scrollHeight,ch:el.clientHeight,overflow:s.overflow,clamp:s.webkitLineClamp,left:r.left,right:r.right}}''')
    assert d['scroll']<=d['client']+1 and d['sh']<=d['ch']+1 and d['clamp'] in ('none','unset',''),d
    assert d['left']>=-1 and d['right']<=await locator.page.evaluate('innerWidth')+1,d
async def run_layout(page):
    c=load();contexts=[]
    try:
        for role in ('public','student'):
            ctx,p=await context(page,c,'student',cookie=role!='public');contexts.append(ctx)
            for width in (390,1000,1920):
                for label in ('long','normal'):
                    name=f'{role} {label} course detail @{width}'
                    try:
                        await p.set_viewport_size({'width':width,'height':844 if width==390 else 1080});await p.goto(BASE+'/courses/'+c['ids'][label]);await p.get_by_test_id('course-detail-title').wait_for();await settled(p)
                        await width_ok(p);title=c['title'] if label=='long' else c['tag']+' normal';await text_ok(p.get_by_test_id('course-detail-title'),title);await text_ok(p.get_by_test_id('course-breadcrumb-title'),title)
                        panel=p.locator('.purchase-panel');await panel.scroll_into_view_if_needed();assert await panel.is_visible();assert await panel.evaluate('e=>e.getBoundingClientRect().left>=0 && e.getBoundingClientRect().right<=innerWidth')
                        assert not await errors(p);record(name)
                        if label=='long':
                            await p.get_by_test_id('course-detail-title').scroll_into_view_if_needed();await shot(p,f'{role}-long-title-{width}');await panel.scroll_into_view_if_needed();await shot(p,f'{role}-long-panel-{width}')
                    except Exception as e:record(name,False,e)
        ctx,p=await context(page,c,'visitor');contexts.append(ctx)
        for width in (390,1000,1920):
            for route,field,label in [('/courses','courses-search','catalog'),('/dashboard/courses','my-courses-search','library')]:
                try:
                    await p.set_viewport_size({'width':width,'height':844 if width==390 else 1080});await p.goto(BASE+route);await p.get_by_test_id(field).fill(c['tag']);title=p.get_by_test_id('course-title-'+c['ids']['long']);await title.wait_for();await settled(p);await text_ok(title,c['title']);await width_ok(p);await title.scroll_into_view_if_needed();await shot(p,f'visitor-{label}-long-{width}');record(f'{label} full long title @{width}')
                except Exception as e:record(f'{label} full long title @{width}',False,e)
        for width in (390,1920):
            try:
                await p.set_viewport_size({'width':width,'height':844 if width==390 else 1080});await p.goto(BASE+'/dashboard');await settled(p)
                assert await p.get_by_test_id('workspace-profile').count()==1 and await p.get_by_test_id('workspace-header-profile').count()==1
                for selector in ('workspace-profile','workspace-header-profile'):
                    await p.get_by_test_id(selector).click();await p.wait_for_url('**/dashboard/profile');await p.get_by_test_id('profile-full-name').fill(c['tag']+f' profile {width} {selector}')
                    async with p.expect_response(lambda r:r.url.endswith('/api/auth/profile') and r.request.method=='PUT') as saved:await p.get_by_test_id('save-profile').click()
                    r=await saved.value;assert r.status==200;expected=c['tag']+f' profile {width} {selector}';assert (await me(p))['name']==expected;await p.get_by_test_id('profile-name').get_by_text(expected,exact=True).wait_for();record(f'{selector} unique navigation/save @{width}')
                await shot(p,f'visitor-profile-{width}')
            except Exception as e:record(f'profile selector sequence @{width}',False,e)
    finally:
        for ctx in contexts:await ctx.close()
        report('layout_profile_browser')
def png():
    def chunk(k,d):return struct.pack('>I',len(d))+k+d+struct.pack('>I',zlib.crc32(k+d)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\xff'))+chunk(b'IEND',b'')
async def run_signup(page):
    c=load();contexts=[]
    try:
        actx,admin=await context(page,c,'admin');contexts.append(actx)
        for mode,width in [('typed',1920),('calendar',390)]:
            role='ui_pending_'+mode;suffix=secrets.token_hex(5);email=c['tag'].lower()+suffix+'@example.com';name=c['tag']+' pending '+mode;phone='+1778'+str(secrets.randbelow(90000000)+10000000)
            ctx,p=await context(page,c,'admin',width,cookie=False);contexts.append(ctx)
            try:
                await p.goto(BASE+'/register')
                for selector,value in [('register-name',name),('auth-email',email),('register-phone',phone),('auth-password',c['password'])]:await p.get_by_test_id(selector).fill(value)
                await p.get_by_test_id('register-avatar').set_input_files({'name':'TEST_avatar.png','mimeType':'image/png','buffer':png()});await p.get_by_test_id('register-is-student').check()
                for selector,value in [('register-university','TEST university'),('register-field','TEST medicine'),('register-krc','KRC'+suffix.upper()),('register-date','2025-01-10')]:await p.get_by_test_id(selector).fill(value)
                expected='2025-01-10'
                if mode=='calendar':
                    await p.get_by_test_id('register-date-calendar-button').click();await p.wait_for_timeout(200);await p.get_by_test_id('register-date-calendar').locator('button').filter(has_text=re.compile('^15$')).click(force=True);await p.get_by_test_id('register-date-calendar').wait_for(state='hidden');await p.wait_for_timeout(350);expected='2025-01-15'
                assert await p.get_by_test_id('register-date').input_value()==expected
                validity=await p.get_by_test_id('auth-form').evaluate('''f=>({valid:f.checkValidity(),invalid:Array.from(f.elements).filter(e=>e.validity&&!e.validity.valid).map(e=>({id:e.id,type:e.type,message:e.validationMessage,pattern:e.pattern}))})''');print('FORM_VALIDITY',mode,validity)
                assert validity['valid'],validity
                submit=p.get_by_test_id('auth-submit');await submit.scroll_into_view_if_needed();await p.wait_for_timeout(350)
                async with p.expect_response(lambda r:r.url.endswith('/api/auth/register') and r.request.method=='POST',timeout=20000) as registered:await submit.click()
                r=await registered.value;row=await r.json();assert r.status==200,(r.status,row);c['accounts'][role]={'id':row['id'],'name':name,'email':email,'phone':phone};save(c)
                await p.wait_for_url('**/dashboard',timeout=30000);await p.get_by_test_id('student-pending-notice').wait_for();state=await me(p)
                assert state['role']=='visitor' and state['student_status']=='pending' and state['avatar_id'] and state['registration_date']==expected
                c['cookies'][role]={'kura_session':next(x['value'] for x in await ctx.cookies() if x['name']=='kura_session')};save(c)
                await shot(p,f'pending-{mode}-registered-{width}');record(f'{mode} actual signup POST/avatar/date/pending @{width}')
                await p.goto(BASE+'/courses/'+c['ids']['normal']);await p.get_by_test_id('course-purchase').wait_for();assert await p.get_by_test_id('view-lecture-'+c['ids']['video_lecture']).count()==0
                data=await p.evaluate("async id=>(await fetch('/api/courses/'+id)).json()",c['ids']['normal']);assert not data['has_access'];record(mode+' pending flagged course denied')
                await admin.goto(BASE+'/admin/users');await admin.get_by_test_id('users-search').fill(email);await admin.get_by_test_id('edit-user-'+row['id']).click();await admin.get_by_test_id('approve-student').click();await admin.get_by_test_id('user-editor').wait_for(state='hidden');await admin.get_by_test_id('user-role-'+row['id']).get_by_text('طالب كورا',exact=True).wait_for();record(mode+' admin UI approval')
                await p.goto(BASE+'/dashboard');await p.get_by_test_id('logout').click();await p.wait_for_url('**/login');assert (await p.request.get(BASE+'/api/auth/me')).status==401;record(mode+' logout revokes session')
                await login(p,c,role);c['cookies'][role]={'kura_session':next(x['value'] for x in await ctx.cookies() if x['name']=='kura_session')};save(c);state=await me(p);assert state['role']=='student' and state['student_status']=='approved';await p.goto(BASE+'/courses/'+c['ids']['normal']);await p.get_by_test_id('course-access-granted').wait_for();await p.get_by_test_id('view-lecture-'+c['ids']['video_lecture']).wait_for();await shot(p,f'approved-{mode}-access-{width}');record(mode+' real login approved student access')
            except Exception as e:
                print('SIGNUP_DIAGNOSTIC',await p.get_by_test_id('auth-form').evaluate('''f=>({valid:f.checkValidity(),invalid:Array.from(f.elements).filter(e=>e.validity&&!e.validity.valid).map(e=>({id:e.id,message:e.validationMessage,pattern:e.pattern}))})''') if await p.get_by_test_id('auth-form').count() else 'No form')
                await errors(p);record(mode+' pending signup sequence',False,repr(e))
    finally:
        save(c)
        for ctx in contexts:await ctx.close()
        report('pending_signup_browser')
async def run_employee_video(page):
    c=load();contexts=[]
    try:
        actx,admin=await context(page,c,'admin');contexts.append(actx)
        try:
            await admin.goto(BASE+'/admin/users');await admin.get_by_test_id('users-search').fill(c['tag']);await admin.get_by_test_id('create-employee').click();await admin.get_by_test_id('user-editor').wait_for();await admin.wait_for_timeout(350)
            role='ui_employee';email=c['tag'].lower()+secrets.token_hex(4)+'employee@example.com';name=c['tag']+' UI employee';phone='+1666'+str(secrets.randbelow(90000000)+10000000)
            for selector,value in [('edit-user-name',name),('edit-user-email',email),('edit-user-phone',phone),('employee-password',c['password'])]:await admin.get_by_test_id(selector).fill(value)
            async with admin.expect_response(lambda r:r.url.endswith('/api/admin/employees') and r.request.method=='POST') as created:await admin.get_by_test_id('save-user').click()
            r=await created.value;row=await r.json();assert r.status==200 and row['role']=='employee';c['accounts'][role]={'id':row['id'],'email':email,'name':name,'phone':phone};save(c)
            await admin.get_by_test_id('user-editor').wait_for(state='hidden');await admin.get_by_test_id('users-search').fill(email);await admin.get_by_test_id('user-row-'+row['id']).wait_for();record('admin actual UI employee creation')
            await admin.set_viewport_size({'width':390,'height':844});await admin.get_by_test_id('edit-user-'+row['id']).click();await admin.wait_for_timeout(350);edited=c['tag']+' edited UI employee';await admin.get_by_test_id('edit-user-name').fill(edited)
            async with admin.expect_response(lambda r:r.url.endswith('/api/admin/users/'+row['id']) and r.request.method=='PATCH') as saved:await admin.get_by_test_id('save-user').click()
            r=await saved.value;assert r.status==200 and (await r.json())['name']==edited;await admin.get_by_test_id('user-editor').wait_for(state='hidden');await admin.get_by_test_id('user-row-'+row['id']).get_by_text(edited,exact=True).wait_for();await shot(admin,'admin-employee-edited-390');record('admin actual UI employee edit persisted @390')
            employee_pages=[]
            for width in (390,1920):
                ctx,p=await context(page,c,role,width,cookie=False);contexts.append(ctx);await login(p,c,role);state=await me(p);assert state['role']=='employee' and state['name']==edited and state['status']=='active';assert await p.get_by_test_id('workspace-payments').count()==0 and await p.get_by_test_id('workspace-courses').count()==0;await width_ok(p);await shot(p,f'employee-active-login-{width}');employee_pages.append(p);record(f'employee actual browser login before inactive @{width}')
            await admin.set_viewport_size({'width':1920,'height':1080});await admin.get_by_test_id('edit-user-'+row['id']).click();await admin.wait_for_timeout(350);await admin.get_by_test_id('edit-user-status').select_option('inactive',force=True)
            async with admin.expect_response(lambda r:r.url.endswith('/api/admin/users/'+row['id']) and r.request.method=='PATCH') as disabled:await admin.get_by_test_id('save-user').click()
            r=await disabled.value;assert r.status==200 and (await r.json())['status']=='inactive';await admin.get_by_test_id('user-editor').wait_for(state='hidden');await admin.get_by_test_id('user-status-'+row['id']).get_by_text('غير نشط',exact=True).wait_for();await shot(admin,'admin-employee-disabled-1920');record('admin actual UI employee disable persisted')
            for p in employee_pages:assert (await p.request.get(BASE+'/api/auth/me')).status==401
            record('employee disable revoked both existing browser sessions')
            for notice_role in (role,'blocked'):
                for width in (390,1920):
                    ctx,p=await context(page,c,notice_role,width,cookie=False);contexts.append(ctx);await p.goto(BASE+'/login');await p.get_by_test_id('auth-email').fill(c['accounts'][notice_role]['email']);await p.get_by_test_id('auth-password').fill(c['password'])
                    async with p.expect_response(lambda r:r.url.endswith('/api/auth/login') and r.request.method=='POST') as denied:await p.get_by_test_id('auth-submit').click()
                    r=await denied.value;assert r.status==403 and 'detail' in await r.json();await p.get_by_test_id('error-notice').wait_for();assert 'موقوف' in await p.get_by_test_id('error-notice').inner_text();await p.get_by_test_id('auth-password').fill('');await width_ok(p);await p.get_by_test_id('error-notice').scroll_into_view_if_needed();await shot(p,f'{notice_role}-notice-{width}');assert (await p.request.get(BASE+'/api/auth/me')).status==401;record(f'{notice_role} actual denied login notice @{width}')
        except Exception as e:await errors(admin);record('employee browser lifecycle sequence',False,repr(e))
        for width in (390,1920):
            ctx,p=await context(page,c,'student',width);contexts.append(ctx)
            try:
                await p.goto(BASE+'/courses/'+c['ids']['normal']);await p.get_by_test_id('view-lecture-'+c['ids']['video_lecture']).click();video=p.get_by_test_id('lecture-video');await video.wait_for(timeout=20000);await video.scroll_into_view_if_needed()
                await p.wait_for_function("()=>{const v=document.querySelector('[data-testid=lecture-video]');return v && Number.isFinite(v.duration) && v.duration>0}",timeout=30000)
                metadata=await video.evaluate('v=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,ready:v.readyState})');assert 7.5<=metadata['duration']<=8.5 and metadata['width']==320
                await video.evaluate('async v=>{v.muted=true;await v.play()}');await p.wait_for_timeout(1200);playing=await video.evaluate('v=>({time:v.currentTime,paused:v.paused,error:v.error?.message})');assert playing['time']>.5 and not playing['paused'] and not playing['error'],playing
                await video.evaluate('v=>{v.pause();v.currentTime=5}');await p.wait_for_function("()=>Math.abs(document.querySelector('[data-testid=lecture-video]').currentTime-5)<.3 && !document.querySelector('[data-testid=lecture-video]').seeking",timeout=15000)
                await video.evaluate('async v=>await v.play()');await p.wait_for_timeout(700);after=await video.evaluate('v=>v.currentTime');assert after>5.3;await video.evaluate('v=>v.pause()');await width_ok(p);await video.scroll_into_view_if_needed();await shot(p,f'student-video-play-seek-{width}');record(f'real protected MP4 finite duration/play/seek @{width}');print('VIDEO_METRICS',width,metadata,playing,after)
            except Exception as e:await errors(p);record(f'real protected MP4 @{width}',False,repr(e))
    finally:
        save(c)
        for ctx in contexts:await ctx.close()
        report('employee_video_browser')