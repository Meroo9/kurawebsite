# Full-site browser evidence, actual UI workflows and role/viewport comparisons.
import json,re,secrets,sys,struct,zlib
from pathlib import Path
from urllib.parse import urlparse
ROOT=Path('/app/test_reports/full_site_roles')
BASE=next(line.split('=',1)[1].strip() for line in Path('/app/frontend/.env').read_text().splitlines() if line.startswith('REACT_APP_BACKEND_URL=')).rstrip('/')
def load():return json.loads((ROOT/'private_state.json').read_text())
def save(c):(ROOT/'private_state.json').write_text(json.dumps(c))
def png():
    def chunk(k,d):return struct.pack('>I',len(d))+k+d+struct.pack('>I',zlib.crc32(k+d)&0xffffffff)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\x00\x00\xff'))+chunk(b'IEND',b'')

results=[]
screens=[]
def record(name,passed=True,error=''):
    results.append({'check':name,'passed':passed,'error':str(error)});print(('PASS ' if passed else 'FAIL ')+name+((': '+str(error)) if error else ''))

async def shot(p,name):
    await p.wait_for_timeout(600)
    path=ROOT/(name+'.jpg');await p.screenshot(path=str(path),quality=40,full_page=False);screens.append(str(path))

def report(name):
    (ROOT/(name+'.json')).write_text(json.dumps({'checks':results,'screenshots':screens},indent=2,ensure_ascii=False))

async def errors(p):
    text=await p.evaluate('''() => { const errorElements = Array.from(document.querySelectorAll('.error, [class*="error"], [id*="error"]')); return errorElements.map(el => el.textContent).join(', '); }''')
    print('Found error message: '+text if text else 'No error messages found on the page');return text

async def settled(p):
    await p.wait_for_timeout(220)
    await p.get_by_test_id('loading-state').first.wait_for(state='hidden',timeout=15000)

async def login(p,state,role):
    await p.goto(BASE+'/login');await p.get_by_test_id('auth-email').fill(state['accounts'][role]['email']);await p.get_by_test_id('auth-password').fill(state['password']);await p.get_by_test_id('auth-submit').click(force=True)
    await p.wait_for_url(re.compile('/(admin|dashboard)$'),timeout=15000)

async def context_for(page,state,role,actual_login=False):
    ctx=await page.context.browser.new_context(viewport={'width':1920,'height':1080})
    if not actual_login:
        await ctx.add_cookies([{'name':'kura_session','value':state['cookies'][role]['kura_session'],'domain':urlparse(BASE).hostname,'path':'/api','secure':True,'httpOnly':True,'sameSite':'Lax'}])
    p=await ctx.new_page();p.on('dialog',lambda d:d.accept())
    if actual_login:await login(p,state,role)
    return ctx,p

async def run_public(page):
    c=load();routes=['/','/about','/services','/courses','/courses/'+c['ids']['course'],'/research','/posts','/posts/'+c['ids']['post'],'/pricing','/contact','/privacy','/login','/register','/forgot-password','/reset-password']
    try:
        for width,height in [(390,844),(1000,1024),(1920,1080)]:
            await page.set_viewport_size({'width':width,'height':height})
            for route in routes:
                label='public '+route+' @'+str(width)
                try:
                    await page.goto(BASE+route);await settled(page)
                    selector='hero-title' if route=='/' else ('auth-title' if route in ('/login','/register','/forgot-password','/reset-password') else ('course-detail-title' if route.startswith('/courses/') else ('post-title-'+c['ids']['post'] if route.startswith('/posts/') else 'page-title')))
                    await page.get_by_test_id(selector).wait_for(timeout=10000)
                    assert not await errors(page)
                    assert await page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow'
                    assert await page.locator('html').get_attribute('dir')=='rtl'
                    broken=await page.locator('img').evaluate_all('(els)=>els.filter(i=>i.complete && i.naturalWidth===0).map(i=>i.getAttribute("src"))');assert not broken,broken
                    record(label)
                    if route in ('/','/posts'):await shot(page,('public-home' if route=='/' else 'public-posts')+'-'+str(width))
                except Exception as e:record(label,False,e)
        await page.set_viewport_size({'width':390,'height':844});await page.goto(BASE+'/')
        for target in ('about','services','courses','research','posts','pricing','contact','home'):
            await page.get_by_test_id('mobile-menu').click(force=True);await page.get_by_test_id('nav-'+target).click(force=True);await settled(page)
            assert page.url.rstrip('/')==BASE+('' if target=='home' else '/'+target)
        record('public actual mobile menu navigation all eight links')
        await page.goto(BASE+'/courses/'+c['ids']['course']);await page.get_by_test_id('course-purchase').click(force=True);await page.wait_for_url('**/login');record('anonymous purchase login gating')
        await page.goto(BASE+'/research');await page.get_by_test_id('research-sign-in').click(force=True);await page.wait_for_url('**/login');record('anonymous research login gating')
        await page.goto(BASE+'/posts/'+c['ids']['post']);await page.get_by_test_id('comment-login-notice').wait_for();assert await page.get_by_test_id('comment-body').count()==0;record('anonymous comments gated')
        await page.goto(BASE+'/admin/users');await page.wait_for_url('**/login');record('anonymous admin UI redirect')
        await page.goto(BASE+'/TEST_UNKNOWN_ROUTE');await page.get_by_test_id('not-found-home').click(force=True);await page.get_by_test_id('hero-title').wait_for();record('not-found home recovery')
    except Exception as e:record('public interaction sequence',False,e)
    finally:report('public_browser')

async def run_roles(page):
    c=load()
    routes={'visitor':['/dashboard','/dashboard/courses','/dashboard/payments','/dashboard/profile','/dashboard/research','/dashboard/research/new','/dashboard/research/'+c['ids']['employee_layout']],
            'pending':['/dashboard','/dashboard/courses','/dashboard/payments','/dashboard/profile','/dashboard/research','/dashboard/research/new'],
            'student':['/dashboard','/dashboard/courses','/dashboard/payments','/dashboard/profile','/dashboard/research','/dashboard/research/new','/dashboard/research/'+c['ids']['main']],
            'employee1':['/dashboard','/dashboard/profile','/dashboard/research','/dashboard/research/'+c['ids']['employee_layout']],
            'employee2':['/dashboard','/dashboard/profile','/dashboard/research'],
            'admin':['/admin','/admin/users','/admin/courses','/admin/courses/'+c['ids']['course'],'/admin/categories','/admin/purchases','/admin/audit','/admin/settings','/admin/research','/admin/research/'+c['ids']['employee_layout'],'/admin/posts']}
    try:
        for role,paths in routes.items():
            ctx,p=await context_for(page,c,role)
            try:
                for width,height in [(390,844),(1000,1024),(1920,1080)]:
                    await p.set_viewport_size({'width':width,'height':height})
                    for route in paths:
                        label=role+' '+route+' @'+str(width)
                        try:
                            await p.goto(BASE+route);await p.get_by_test_id('page-title').wait_for(timeout=15000);await settled(p)
                            # Filter private admin lists to this run before evidence is captured.
                            field={'/admin/users':'users-search','/admin/courses':'admin-courses-search','/admin/purchases':'purchases-search','/admin/audit':'audit-search','/admin/research':'research-search','/admin/posts':'admin-posts-search'}.get(route)
                            if field:
                                await p.get_by_test_id(field).fill(c['tag']);await p.wait_for_timeout(300)
                            assert not await errors(p)
                            assert await p.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Horizontal overflow'
                            if role=='employee1':assert await p.get_by_test_id('research-payment-status').count()==0
                            if role.startswith('employee'):assert await p.get_by_test_id('workspace-payments').count()==0 and await p.get_by_test_id('workspace-courses').count()==0
                            if role=='pending' and route=='/dashboard':await p.get_by_test_id('student-pending-notice').wait_for()
                            if role=='student' and route=='/dashboard/profile':assert await p.get_by_test_id('profile-krc').is_disabled()
                            record(label)
                            if width in (390,1920):
                                wanted=(role=='visitor' and route=='/dashboard') or (role=='pending' and route=='/dashboard/profile') or (role=='student' and route=='/dashboard/courses') or (role.startswith('employee') and '/research' in route) or (role=='admin' and route in ('/admin','/admin/users','/admin/purchases','/admin/research','/admin/posts')) or route.endswith(c['ids']['employee_layout'])
                                if wanted:await shot(p,role+'-'+route.strip('/').replace('/','-')+'-'+str(width))
                        except Exception as e:record(label,False,e)
                if role!='admin':
                    for path in ('/admin','/admin/users','/admin/research','/admin/posts','/admin/settings'):
                        try:
                            await p.goto(BASE+path);await p.wait_for_url('**/dashboard',timeout=10000);await settled(p);record(role+' direct UI '+path+' denied')
                        except Exception as e:record(role+' direct UI '+path+' denied',False,e)
                if role=='employee1':
                    await p.goto(BASE+'/dashboard/research');await p.get_by_test_id('assigned-research-tab').click(force=True);await p.get_by_test_id('research-row-'+c['ids']['employee_layout']).wait_for();record('employee assigned tab navigation')
                    await shot(p,'employee1-assigned-list-1920')
                if role in ('visitor','pending','student'):
                    await p.goto(BASE+'/dashboard');data=await p.evaluate("async()=> (await fetch('/api/my/library')).json()")
                    await p.get_by_test_id('my-course-count').get_by_text(str(data['total']),exact=True).wait_for(timeout=10000);record(role+' dashboard actual library count')
            except Exception as e:record(role+' remaining interaction sequence',False,e)
            finally:await ctx.close()
        for role in ('blocked','inactive'):
            ctx=await page.context.browser.new_context(viewport={'width':390,'height':844});p=await ctx.new_page()
            try:
                await p.goto(BASE+'/login');await p.get_by_test_id('auth-email').fill(c['accounts'][role]['email']);await p.get_by_test_id('auth-password').fill(c['password']);await p.get_by_test_id('auth-submit').click(force=True)
                await p.get_by_test_id('error-notice').wait_for();assert 'موقوف' in await p.get_by_test_id('error-notice').inner_text();await p.get_by_test_id('auth-password').fill('');await shot(p,role+'-notice-390');record(role+' login denied with notice')
                await p.goto(BASE+'/posts/'+c['ids']['post']);await p.get_by_test_id('post-title-'+c['ids']['post']).wait_for();record(role+' public read remains available')
            except Exception as e:record(role+' login/public checks',False,e)
            finally:await ctx.close()
    finally:report('roles_browser')

async def run_role_followup(page):
    c=load()
    try:
        for role in ('visitor','pending','student','employee2'):
            ctx,p=await context_for(page,c,role)
            try:
                if role=='employee2':
                    await p.set_viewport_size({'width':390,'height':844});await p.goto(BASE+'/dashboard/profile');await p.get_by_test_id('page-title').wait_for(timeout=15000);assert not await errors(p);record('employee2 /dashboard/profile @390 retry')
                else:
                    await p.goto(BASE+'/dashboard');data=await p.evaluate("async()=> (await fetch('/api/my/library')).json()")
                    await p.get_by_test_id('my-course-count').get_by_text(str(data['total']),exact=True).wait_for(timeout=10000);record(role+' dashboard actual library count')
            except Exception as e:record(role+' followup',False,e)
            finally:await ctx.close()
    finally:report('role_followup')

async def run_accounts_courses(page,students=(False,True)):
    c=load();contexts=[]
    try:
        for student in students:
            ctx=await page.context.browser.new_context(viewport={'width':390,'height':844});contexts.append(ctx);p=await ctx.new_page();suffix=secrets.token_hex(5);role='ui_pending' if student else 'ui_visitor'
            if role in c['accounts']:
                oldrole=role+'_previous_'+suffix;c['accounts'][oldrole]=c['accounts'].pop(role);c['cookies'][oldrole]=c['cookies'].pop(role,{})
            email=c['tag'].lower()+suffix+'@example.com';phone='+1778'+str(secrets.randbelow(90000000)+10000000);name=c['tag']+' UI '+role
            await p.goto(BASE+'/register');await p.get_by_test_id('register-name').fill(name);await p.get_by_test_id('auth-email').fill(email);await p.get_by_test_id('register-phone').fill(phone);await p.get_by_test_id('auth-password').fill(c['password'])
            await p.get_by_test_id('register-avatar').set_input_files({'name':'TEST_UI_avatar.png','mimeType':'image/png','buffer':png()})
            if student:
                await p.get_by_test_id('register-is-student').check(force=True);await p.get_by_test_id('register-university').fill('TEST university');await p.get_by_test_id('register-field').fill('TEST medicine');await p.get_by_test_id('register-krc').fill('KRC'+suffix.upper());date=p.get_by_test_id('register-date');assert await date.get_attribute('type')=='text';await date.fill('2025-01-10')
                await p.get_by_test_id('register-date-calendar-button').click(force=True);await p.wait_for_timeout(200);await p.get_by_test_id('register-date-calendar').locator('button').filter(has_text=re.compile('^15$')).click(force=True);assert await date.input_value()=='2025-01-15'
                record('pending student custom calendar works')
            # Register response captured before optional avatar upload: track fixture immediately.
            async with p.expect_response(lambda r:r.url.endswith('/api/auth/register') and r.request.method=='POST') as created:await p.get_by_test_id('auth-submit').click(force=True)
            response=await created.value;row=await response.json();assert response.status==200
            c['accounts'][role]={'id':row['id'],'email':email,'name':name,'phone':phone};save(c)
            await p.wait_for_url('**/dashboard',timeout=30000);await settled(p)
            me=await p.evaluate("async()=> (await fetch('/api/auth/me')).json()")
            assert me['role']=='visitor' and me['student_status']==('pending' if student else 'none') and me['avatar_id']
            c['cookies'][role]={'kura_session':next(x['value'] for x in await ctx.cookies() if x['name']=='kura_session')};save(c)
            await shot(p,role+'-registration-dashboard-390');record(role+' actual registration avatar and permission state')
            await p.get_by_test_id('workspace-profile').first.click(force=True);await p.get_by_test_id('profile-full-name').fill(name+' edited');await p.get_by_test_id('save-profile').click(force=True);await p.get_by_test_id('profile-name').get_by_text(name+' edited',exact=True).wait_for();record(role+' UI profile save persistence')
            await p.goto(BASE+'/dashboard');await settled(p)
            await p.get_by_test_id('logout').click(force=True);await p.wait_for_url('**/login');r=await p.request.get(BASE+'/api/auth/me');assert r.status==401;record(role+' logout revokes session')
            await login(p,c,role);c['cookies'][role]={'kura_session':next(x['value'] for x in await ctx.cookies() if x['name']=='kura_session')};save(c);record(role+' actual login after logout')
        admin_ctx,admin=await context_for(page,c,'admin',actual_login=True);contexts.append(admin_ctx)
        await admin.goto(BASE+'/admin/users');await admin.get_by_test_id('users-search').fill(c['accounts']['ui_pending']['email']);uid=c['accounts']['ui_pending']['id'];await admin.get_by_test_id('edit-user-'+uid).click(force=True)
        await admin.get_by_test_id('approve-student').click(force=True);await admin.get_by_test_id('user-editor').wait_for(state='hidden');await admin.get_by_test_id('user-role-'+uid).get_by_text('طالب كورا',exact=True).wait_for();record('admin UI approval promotes only isolated pending student')
        await admin.get_by_test_id('edit-user-'+uid).click(force=True);await admin.get_by_test_id('admin-krc-input').fill('KRC'+secrets.token_hex(7).upper());await admin.get_by_test_id('save-krc-correction').click(force=True);await admin.get_by_test_id('user-editor').wait_for(state='hidden');record('admin UI KRC correction')
        # Actual course create/edit/publish and lecture upload, with every returned ID retained.
        await admin.goto(BASE+'/admin/courses');await admin.get_by_test_id('create-course').click(force=True);title=c['tag']+' '+('عنوانكورسطويل'*10)
        await admin.get_by_test_id('course-title-input').fill(title);await admin.get_by_test_id('course-description-input').fill('TEST UI comprehensive medical course with long Arabic title');await admin.get_by_test_id('course-category-input').select_option(c['ids']['category']);await admin.get_by_test_id('course-price-input').fill('8.50')
        async with admin.expect_response(lambda r:r.url.endswith('/api/admin/courses') and r.request.method=='POST') as created:await admin.get_by_test_id('save-course').click(force=True)
        r=await created.value;row=await r.json();assert r.status==200;cid=row['id'];c['course_ids'].append(cid);c['ids']['ui_course']=cid;save(c);await admin.get_by_test_id('course-editor').wait_for(state='hidden');record('admin UI draft course creation')
        await admin.get_by_test_id('admin-courses-search').fill(c['tag']);await admin.get_by_test_id('edit-course-'+cid).click(force=True);await admin.get_by_test_id('course-published').check(force=True);await admin.get_by_test_id('save-course').click(force=True);await admin.get_by_test_id('course-editor').wait_for(state='hidden');record('admin UI course publish')
        await admin.get_by_test_id('manage-lectures-'+cid).click(force=True);await admin.get_by_test_id('add-lecture').click(force=True);await admin.get_by_test_id('lecture-title-input').fill('TEST UI medical lecture');await admin.get_by_test_id('lecture-file-input').set_input_files({'name':'TEST_UI_lecture.txt','mimeType':'text/plain','buffer':b'TEST UI private lecture'})
        async with admin.expect_response(lambda r:r.url.endswith('/lectures') and r.request.method=='POST') as created:await admin.get_by_test_id('save-lecture').click(force=True)
        r=await created.value;lecture=await r.json();assert r.status==200;await admin.get_by_test_id('lecture-editor').wait_for(state='hidden');c['ids']['ui_lecture']=lecture['id'];save(c);record('admin UI actual lecture upload')
        member_ctx,member=await context_for(page,c,'other',actual_login=True);contexts.append(member_ctx)
        pid=c['ids']['other_purchase'];await member.goto(BASE+'/courses/'+c['ids']['course']);await member.get_by_test_id('receipt-file-'+pid).wait_for();assert await member.get_by_test_id('course-purchase').count()==0;record('exact older purchase UI found beyond page15')
        for decision in ('rejected','approved'):
            await member.get_by_test_id('receipt-file-'+pid).set_input_files({'name':'TEST_UI_receipt.png','mimeType':'image/png','buffer':png()});await member.get_by_test_id('receipt-submit-'+pid).click(force=True);await member.get_by_test_id('purchase-status').get_by_text('قيد المراجعة',exact=True).wait_for(timeout=30000)
            assert await member.get_by_test_id('view-lecture-'+c['ids']['lecture']).count()==0;record('whole-course pending locked '+decision)
            await admin.goto(BASE+'/admin/purchases');await admin.get_by_test_id('purchases-search').fill(c['tag']);await admin.get_by_test_id('review-purchase-'+pid).click(force=True);await shot(admin,'admin-course-receipt-'+decision+'-1920')
            if decision=='rejected':await admin.get_by_test_id('receipt-rejection-reason').fill('TEST UI unreadable receipt');await admin.get_by_test_id('reject-receipt').click(force=True)
            else:await admin.get_by_test_id('approve-receipt').click(force=True)
            await admin.get_by_test_id('receipt-review-modal').wait_for(state='hidden');await member.reload();await settled(member);record('actual course receipt '+decision)
        await member.get_by_test_id('course-access-granted').wait_for();await member.get_by_test_id('view-lecture-'+c['ids']['lecture']).click(force=True);await member.get_by_test_id('lecture-document').wait_for(timeout=20000);record('approved whole course private lecture preview')
        async with member.expect_download() as d:await member.get_by_test_id('viewer-download').click(force=True)
        download=await d.value;assert not await download.failure();record('protected lecture real download')
        await member.goto(BASE+'/courses/'+cid)
        for width,height in [(390,844),(1000,1024),(1920,1080)]:
            await member.set_viewport_size({'width':width,'height':height});await settled(member);dimensions=await member.evaluate('({doc:document.documentElement.scrollWidth,viewport:innerWidth})')
            record('long Arabic course title @'+str(width),dimensions['doc']<=dimensions['viewport'],dimensions if dimensions['doc']>dimensions['viewport'] else '')
            await shot(member,'long-course-title-'+str(width))
        # A genuine purchase of the UI-created course is distinct from the older lookup flow.
        await member.get_by_test_id('course-purchase').click(force=True);await member.locator('[data-testid^="receipt-file-"]').wait_for();record('actual UI whole course purchase')
        await member.goto(BASE+'/dashboard/courses');await member.get_by_test_id('my-courses-search').fill(c['tag']+' Library');await member.get_by_test_id('pagination-status').get_by_text('1 / 2',exact=True).wait_for();await member.get_by_test_id('next-page').click(force=True);await member.get_by_test_id('pagination-status').get_by_text('2 / 2',exact=True).wait_for();record('actual library search and page12 navigation')
    except Exception as e:
        import traceback
        record('accounts courses sequence',False,repr(e));print(traceback.format_exc())
    finally:
        save(c)
        for ctx in contexts:await ctx.close()
        report('accounts_courses_browser')

async def run_final(page,include_layout=True):
    c=load();cid=c['ids']['ui_course'];pid=c['ids']['long_post'];ctx,p=await context_for(page,c,'visitor')
    try:
        for width,height in ([(390,844),(1000,1024),(1920,1080)] if include_layout else []):
            await p.set_viewport_size({'width':width,'height':height});await p.goto(BASE+'/posts/'+pid);await p.get_by_test_id('post-title-'+pid).wait_for();await settled(p)
            assert await p.evaluate('document.documentElement.scrollWidth <= innerWidth');assert await p.evaluate('window.TEST_XSS===undefined');record('long post and 1300char comment wraps literal XSS @'+str(width));await shot(p,'long-post-detail-'+str(width))
            await page.set_viewport_size({'width':width,'height':height});await page.goto(BASE+'/courses/'+cid);await page.get_by_test_id('course-detail-title').wait_for();await settled(page)
            measurements=await page.evaluate('''()=>{const h=document.querySelector('[data-testid="course-detail-title"]');const g=document.querySelector('.course-detail-grid');return {doc:document.documentElement.scrollWidth,viewport:innerWidth,scrollX:scrollX,headingWidth:h.getBoundingClientRect().width,headingRight:h.getBoundingClientRect().right,headingWrap:getComputedStyle(h).overflowWrap,gridColumns:getComputedStyle(g).gridTemplateColumns}}''')
            print('COURSE_OVERFLOW',width,measurements)
            record('confirmed public long-course overflow @'+str(width),measurements['doc']<=width,measurements)
            await page.evaluate('scrollTo(0,0)');await shot(page,'long-course-fresh-'+str(width))
        await p.goto(BASE+'/posts/'+c['ids']['pagination_post']);await p.get_by_test_id('pagination-status').get_by_text('1 / 2',exact=True).wait_for();assert await p.locator('.comments-list [data-testid^="comment-body-"]').count()==15
        async with p.expect_response(lambda r:'/comments?page=2' in r.url):await p.get_by_test_id('next-page').click(force=True)
        await p.get_by_test_id('pagination-status').get_by_text('2 / 2',exact=True).wait_for();await p.wait_for_timeout(250);assert await p.locator('.comments-list [data-testid^="comment-body-"]').count()==1;record('actual comments page15 navigation')
        await ctx.grant_permissions(['clipboard-read','clipboard-write'],origin=BASE)
        await p.get_by_test_id('post-share-'+c['ids']['pagination_post']).click(force=True);await p.wait_for_timeout(250);assert await p.evaluate('navigator.clipboard.readText()')==BASE+'/posts/'+c['ids']['pagination_post'];record('actual clipboard share copies canonical post URL')
        await p.goto(BASE+'/posts');await p.get_by_test_id('posts-search').fill(c['tag']+' Pagination');await p.get_by_test_id('pagination-status').get_by_text('1 / 2',exact=True).wait_for();await p.get_by_test_id('next-page').click(force=True);await p.get_by_test_id('pagination-status').get_by_text('2 / 2',exact=True).wait_for();record('actual public posts search page6 navigation')
        await p.goto(BASE+'/courses');await p.get_by_test_id('courses-search').fill(c['tag']+' Library');await p.get_by_test_id('course-results-count').get_by_text('13 كورس',exact=True).wait_for();await p.get_by_test_id('category-filter-'+c['ids']['category']).click(force=True);await p.get_by_test_id('course-results-count').get_by_text('13 كورس',exact=True).wait_for();await p.get_by_test_id('next-page').click(force=True);await p.get_by_test_id('pagination-status').get_by_text('2 / 2',exact=True).wait_for();record('actual course search category page12 navigation')
        await p.goto(BASE+'/dashboard/payments');await p.get_by_test_id('paid-'+c['currency']).wait_for();other='EUR' if c['currency']!='EUR' else 'USD';await p.get_by_test_id('paid-'+other).wait_for();await p.get_by_test_id('research-payments-tab').click(force=True);await p.locator('[data-testid^="research-payment-row-"]').first.wait_for();record('financial tabs and per-currency course totals actual UI')
    except Exception as e:
        record('final independent interactions',False,repr(e))
    finally:
        await ctx.close();report('final_browser' if include_layout else 'final_interactions_browser')