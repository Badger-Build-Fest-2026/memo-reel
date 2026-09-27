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
    database_url = os.getenv("DATABRICKS_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError(
            "DATABRICKS_DATABASE_URL or DATABASE_URL is not configured"
        )

    url = make_url(database_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+asyncpg")
    elif url.get_backend_name() == "postgresql" and url.drivername != "postgresql+asyncpg":
        raise RuntimeError(
            "PostgreSQL SQLAlchemy URLs must use the asyncpg driver, for example "
            "postgresql+asyncpg://user:password@host:5432/database"
        )

    connect_args = {}
    if url.get_backend_name() == "postgresql":
        connect_args = {"timeout": 10, "server_settings": {"timezone": "UTC"}}
        sslmode = url.query.get("sslmode")
        if sslmode is not None:
            supported_sslmodes = {
                "allow",
                "disable",
                "prefer",
                "require",
                "verify-ca",
                "verify-full",
            }
            if not isinstance(sslmode, str) or sslmode not in supported_sslmodes:
                raise RuntimeError(f"Unsupported PostgreSQL sslmode: {sslmode}")
            connect_args["ssl"] = sslmode
            url = url.difference_update_query(["sslmode"])

    if os.getenv("DB_DISABLE_PREPARED_STATEMENTS", "").lower() == "true":
        connect_args["statement_cache_size"] = 0

    database_url = url.render_as_string(hide_password=False)
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
