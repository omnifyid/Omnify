"""
Demo data seeder (one business, three stores). The logic lives in app/services/seed_service.py;
the super admin page runs the same reset.

Run:  uv run python seed.py            # reset demo data, then seed it again
      uv run python seed.py --reset    # same
      uv run python seed.py --clear    # remove demo data only
      uv run python seed.py --admin    # also create admin@demo.com (super admin); password from
                                       # DEMO_ADMIN_PASSWORD, or a random one printed once
"""

import asyncio
import os
import secrets
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.database import AsyncSessionLocal
from app.models import User
from app.services import seed_service


async def main() -> None:
    async with AsyncSessionLocal() as session:
        if "--clear" in sys.argv:
            removed = await seed_service.reset_demo(session)
            print(f"Removed {removed} demo store(s).")
            return
        summary = await seed_service.reseed(session)
        print("Demo data ready:")
        for key, value in summary.items():
            print(f"  {key:16} {value}")
        print("\nLogins (password demo1234): owner@demo.com, manager@demo.com, operator@demo.com,")
        print("  kasir.senopati@demo.com, manager.bsd@demo.com, kasir.bsd@demo.com")
        if "--admin" in sys.argv:
            password = os.environ.get("DEMO_ADMIN_PASSWORD") or secrets.token_urlsafe(12)
            if await session.scalar(select(User.id).where(User.email == "admin@demo.com")):
                print("admin@demo.com already exists; password unchanged.")
            else:
                session.add(User(email="admin@demo.com", full_name="Super Admin",
                                 hashed_password=hash_password(password), is_superadmin=True))
                await session.commit()
                shown = "(from DEMO_ADMIN_PASSWORD)" if os.environ.get("DEMO_ADMIN_PASSWORD") else password
                print(f"Super admin: admin@demo.com / {shown}")


if __name__ == "__main__":
    asyncio.run(main())
