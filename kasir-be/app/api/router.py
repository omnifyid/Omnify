from fastapi import APIRouter

router = APIRouter()

# Routes will be included here as each module is built
from app.api.v1 import admin, auth, users, stores, categories, items, packages, discounts, orders, reports, public, inventory, channels, finance, shifts  # noqa: E402, F401

router.include_router(auth.router, prefix="/auth", tags=["auth"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(admin.user_router, prefix="/admin/users", tags=["admin"])
router.include_router(admin.router, prefix="/admin/stores", tags=["admin"])
router.include_router(admin.seed_router, prefix="/admin/seed", tags=["admin"])
router.include_router(stores.router, prefix="/stores", tags=["stores"])
router.include_router(categories.router, prefix="/stores", tags=["categories"])
router.include_router(items.router, prefix="/stores", tags=["items"])
router.include_router(packages.router, prefix="/stores", tags=["packages"])
router.include_router(discounts.router, prefix="/stores", tags=["discounts"])
router.include_router(orders.router, prefix="/stores", tags=["orders"])
router.include_router(reports.router, prefix="/stores", tags=["reports"])
router.include_router(inventory.router, prefix="/stores", tags=["inventory"])
router.include_router(channels.router, prefix="/stores", tags=["channels"])
router.include_router(finance.router, prefix="/stores", tags=["finance"])
router.include_router(shifts.router, prefix="/stores", tags=["shifts"])
router.include_router(public.router, prefix="/public", tags=["public"])
