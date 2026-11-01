"""Private operator command. Never called by a public HTTP route.

Creates a one-time, expiring owner activation link without shared credentials.
Run only by the platform owner; signing in does not confer admin permissions.
"""
import sys, asyncio, secrets
from pathlib import Path
from datetime import timedelta
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from core import db, now, digest, ORIGIN

async def main():
    if await db.users.count_documents({'role':'admin'}):
        raise SystemExit('Owner already activated; no new invitation was created.')
    await db.owner_invites.delete_many({'used':False})
    token=secrets.token_urlsafe(40)
    await db.owner_invites.insert_one({'token_hash':digest(token),'used':False,'expires_at':now()+timedelta(days=14)})
    print(f'{ORIGIN}/activate-owner#token={token}')

if __name__=='__main__':asyncio.run(main())