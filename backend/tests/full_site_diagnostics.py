# Non-secret session and current-state diagnostics for the full-site harness.
from full_site_support import load, req
from hashlib import sha256
c=load()
for role,a in c['accounts'].items():
    token=c['cookies'].get(role,{}).get('kura_session','')
    print(role,'state_cookie_present',bool(token),'db_session_present',bool(c['db'].sessions.find_one({'user_id':a['id'],'token_hash':sha256(token.encode()).hexdigest()})),'public_me_status',req(c,role,'get','/auth/me').status_code)