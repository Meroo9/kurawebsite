# Diagnostic prints only cookie attributes, never session secrets.
import os,json,requests
from pathlib import Path
from dotenv import load_dotenv
load_dotenv('/app/frontend/.env')
state=json.loads(Path('/app/test_reports/test_state.json').read_text())
r=requests.post(os.environ['REACT_APP_BACKEND_URL']+'/api/auth/login',json={'email':state['accounts']['visitor']['email'],'password':state['password']},timeout=30)
for h in r.raw.headers.getlist('Set-Cookie'):
    if h.startswith('kura_session='):
        print('Cookie attributes:',h.split(';')[1:])