"""
Database connection pool and schema initialization.
Uses PGroonga for full-text search on book titles/tags.
"""
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            os.environ["DATABASE_URL"],
            min_size=2,
            max_size=10,
            command_timeout=30,
        )
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


async def init_schema():
    """Create tables and indexes if they don't exist."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE EXTENSION IF NOT EXISTS pgroonga;

            CREATE TABLE IF NOT EXISTS users (
                id          SERIAL PRIMARY KEY,
                username    TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                totp_secret TEXT NOT NULL,
                created_at  TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS tags (
                id    SERIAL PRIMARY KEY,
                name  TEXT UNIQUE NOT NULL,
                color TEXT NOT NULL DEFAULT '#6366f1'
            );

            CREATE TABLE IF NOT EXISTS books (
                id         SERIAL PRIMARY KEY,
                title      TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS book_tags (
                book_id INT REFERENCES books(id) ON DELETE CASCADE,
                tag_id  INT REFERENCES tags(id)  ON DELETE CASCADE,
                PRIMARY KEY (book_id, tag_id)
            );

            -- PGroonga index for fast full-text search on book titles
            CREATE INDEX IF NOT EXISTS books_pgroonga_idx
                ON books USING pgroonga (title)
                WITH (tokenizer = 'TokenBigram');

            -- Also index tag names for tag search
            CREATE INDEX IF NOT EXISTS tags_pgroonga_idx
                ON tags USING pgroonga (name)
                WITH (tokenizer = 'TokenBigram');
        """)
