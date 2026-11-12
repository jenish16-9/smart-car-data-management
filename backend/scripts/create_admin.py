"""Create one development administrator from temporary environment variables.

Required: ``ADMIN_EMAIL`` and ``ADMIN_PASSWORD``. Optional: ``ADMIN_NAME``.
The password is hashed and never printed or stored in source control.
"""

import asyncio
import os

from app.core.config import settings
from app.core.security import hash_password
from app.db.postgres import dispose_engine, get_sessionmaker
from app.repositories import user_repository


async def main() -> None:
    if settings.environment != "development":
        raise SystemExit("Refusing to bootstrap an administrator unless ENVIRONMENT=development")
    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    name = os.environ.get("ADMIN_NAME", "AudioGuard Admin").strip()
    if not email or "@" not in email:
        raise SystemExit("Set ADMIN_EMAIL to a valid email address")
    if len(password) < 12:
        raise SystemExit("Set ADMIN_PASSWORD to at least 12 characters")
    try:
        async with get_sessionmaker()() as session:
            existing = await user_repository.get_by_email(session, email)
            if existing is not None:
                if existing.role != "admin":
                    raise SystemExit(f"{email} already exists as a non-admin account")
                print(f"Administrator already exists: {email}")
                return
            await user_repository.create(
                session,
                name=name,
                email=email,
                password_hash=hash_password(password),
                role="admin",
            )
            await session.commit()
            print(f"Administrator created: {email}")
    finally:
        await dispose_engine()


if __name__ == "__main__":
    asyncio.run(main())
