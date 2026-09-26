from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.api_endpoints import api_router
from app.db.session import check_db_connection


@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_db_connection()
    yield


app = FastAPI(
    title="RecallGraph API",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router, prefix="/api/v1")
