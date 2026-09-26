import os
from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> AsyncEngine:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is not configured")

    url = make_url(database_url)
    if url.get_backend_name() == "postgresql" and url.drivername != "postgresql+asyncpg":
        raise RuntimeError(
            "DATABASE_URL must use the asyncpg driver, for example "
            "postgresql+asyncpg://user:password@host:5432/dbname"
        )

    connect_args = {}
    if url.get_backend_name() == "postgresql":
        connect_args = {"timeout": 10, "server_settings": {"timezone": "UTC"}}

    return create_async_engine(
        database_url,
        pool_pre_ping=True,
        echo=os.getenv("SQLALCHEMY_ECHO", "").lower() == "true",
        connect_args=connect_args,
    )


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        autoflush=False,
        bind=get_engine(),
        expire_on_commit=False,
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_sessionmaker()() as db:
        yield db


async def check_db_connection() -> None:
    async with get_engine().connect() as connection:
        await connection.execute(text("SELECT 1"))
