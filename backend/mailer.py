import os, re, ipaddress, logging
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse
import httpx
from fastapi import HTTPException

EMAIL_BASE_URL = 'https://integrations.emergentagent.com'
logger = logging.getLogger(__name__)
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv", "send us your password", "enter your password below", "confirm your card number", "your full card number", "seed phrase", "recovery phrase", "verify your card", "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)

def _host_ok(host):
    if not host or 'xn--' in host: return False
    try: ipaddress.ip_address(host); return False
    except ValueError: pass
    return not any(host == s or host.endswith('.' + s) for s in _SHORTENERS)

def _same_site(shown, real):
    return shown == real or real.endswith('.'+shown) or shown.endswith('.'+real)

class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__(); self.tags,self.urls,self.anchors=set(),[],[]; self._href,self._text=None,[]
    def handle_starttag(self,tag,attrs):
        self.tags.add(tag.lower()); self.urls += [v for k,v in attrs if k.lower() in ('href','src') and v]
        if tag.lower()=='a': self._href=dict((k.lower(),v) for k,v in attrs).get('href'); self._text=[]
    def handle_data(self,data):
        if self._href is not None: self._text.append(data)
    def handle_endtag(self,tag):
        if tag.lower()=='a' and self._href is not None:
            self.anchors.append((self._href,''.join(self._text))); self._href,self._text=None,[]

def _assert_safe_email(subject,html):
    scan=_EmailScan(); scan.feed(html)
    if scan.tags & {'form','input','textarea','select'}: raise ValueError('No forms or input fields in email (G2)')
    body=f'{subject}\n{html}'.lower()
    for p in _CRED_ASK:
        if p in body: raise ValueError('Email asks the recipient for credentials (G2)')
    for url in scan.urls:
        low=url.strip().lower()
        if low.startswith(('mailto:','tel:','cid:','#')): continue
        if not low.startswith('https://'): raise ValueError('Email links/assets must be absolute https (G3)')
        host=urlparse(low).hostname or ''
        if not _host_ok(host) or urlparse(low).username is not None: raise ValueError('Unsafe URL (G3)')
    for href,text in scan.anchors:
        real=urlparse(href.strip().lower()).hostname or ''
        if not real: continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(),real): raise ValueError('Anchor text does not match real link host (G3)')

async def send_reset_email(user,link):
    name=os.environ['EMAIL_FROM_NAME']
    subject=f'{name} — استعادة كلمة المرور'
    html=f'''<html dir="rtl"><body><table role="presentation" style="width:100%;background:#f6f8fc"><tr><td style="padding:32px;font-family:Arial,sans-serif;color:#10204c"><h1>{escape(name)}</h1><p>مرحبًا {escape(user['name'])}،</p><p>وصلنا طلب لإعادة تعيين كلمة مرور حسابك في كورا.</p><p><a href="{escape(link,quote=True)}" style="color:#0645c1">إعادة تعيين كلمة المرور</a></p><p>هذا الرابط صالح لمدة 30 دقيقة ويُستخدم مرة واحدة. إن لم تطلب تغيير كلمة المرور، تجاهل هذه الرسالة.</p><p>لن نطلب منك إرسال كلمة المرور أو بيانات الدفع عبر البريد.</p><p>{escape(name)}</p></td></tr></table></body></html>'''
    _assert_safe_email(subject,html)
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            result=await client.post(f'{EMAIL_BASE_URL}/api/v1/email/send',headers={'X-Email-Key':os.environ['EMERGENT_EMAIL_KEY']},json={'to':[user['email']],'subject':subject,'html':html,'from_name':name})
        result.raise_for_status()
        return result.json().get('id')
    except (httpx.HTTPError,KeyError):
        logger.warning('Managed password reset email unavailable')
        raise HTTPException(503,'خدمة البريد غير متاحة مؤقتًا')