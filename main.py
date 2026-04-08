from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db
from routers import analytics, athlete, auth, health, workout_stats, workouts


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="Health Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "capacitor://localhost",   # Capacitor iOS/Android
        "http://localhost",        # Capacitor fallback
        "https://custom-fitness-app-frontend.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(athlete.router)
app.include_router(workouts.router)
app.include_router(workout_stats.router)
app.include_router(health.router)
app.include_router(analytics.router)
