from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.api_endpoints import api_router
from app.db.session import check_db_connection, initialize_database
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_db_connection()
    # await initialize_database()
    yield



app = FastAPI(
    title="MemoReel API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api/v1")
