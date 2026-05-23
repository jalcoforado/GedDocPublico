import asyncio
from app.database import SessionLocal
from app.auth.jwt import build_payload, get_jwt_secret
from jose import jwt as jose_jwt


async def main():
    async with SessionLocal() as db:
        secret = await get_jwt_secret(db)
        payload = build_payload(2, "admin@local.test")
        print(jose_jwt.encode(payload, secret, algorithm="HS256"))


asyncio.run(main())
