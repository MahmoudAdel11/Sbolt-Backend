from fastapi import APIRouter

from app.api.v1.routes import auth, drivers, favorite_places, health, rides, users

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(drivers.router)
api_router.include_router(rides.router)
api_router.include_router(favorite_places.router)
