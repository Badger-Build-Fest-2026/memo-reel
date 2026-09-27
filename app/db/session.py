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
    database_url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("SUPABASE_DATABASE_URL is not configured")

    url = make_url(database_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")
        database_url = url.render_as_string(hide_password=False)
    elif url.get_backend_name() == "postgresql" and url.drivername != "postgresql+asyncpg":
        raise RuntimeError(
            "Supabase SQLAlchemy URLs must use the asyncpg driver, for example "
            "postgresql+asyncpg://postgres:password@db.project-ref.supabase.co:5432/postgres"
        )

    connect_args = {}
    if url.get_backend_name() == "postgresql":
        connect_args = {"timeout": 10, "server_settings": {"timezone": "UTC"}}

    is_supabase_host = url.host is not None and "supabase" in url.host
    is_supabase_pooler = (
        url.host is not None
        and "pooler.supabase.com" in url.host
        and url.port == 6543
    )
    if is_supabase_host and os.getenv("SUPABASE_SSL", "true").lower() != "false":
        connect_args["ssl"] = True
    if (
        is_supabase_pooler
        or os.getenv("DB_DISABLE_PREPARED_STATEMENTS", "").lower() == "true"
    ):
        connect_args["statement_cache_size"] = 0

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
