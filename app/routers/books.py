"""
Books routes:
- GET  /          → library homepage
- GET  /api/search → real-time search (PGroonga)
- POST /api/books  → add book
- PUT  /api/books/{id} → update book
- DELETE /api/books/{id} → delete book
"""
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from app.database import get_pool
from app.auth import get_current_user, require_user

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class BookIn(BaseModel):
    title: str
    tag_ids: list[int] = []


class BookUpdate(BaseModel):
    title: str | None = None
    tag_ids: list[int] | None = None


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    # If get_current_user returned a redirect, pass it through
    if isinstance(user, RedirectResponse):
        return user
    pool = await get_pool()
    async with pool.acquire() as conn:
        tags = await conn.fetch("SELECT id, name, color FROM tags ORDER BY name")
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        "tags": [dict(t) for t in tags],
    })


@router.get("/api/search")
async def search(
    request: Request,
    q: str = "",
    tag_id: int | None = None,
    user=Depends(require_user),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if q.strip():
            rows = await conn.fetch("""
                SELECT b.id, b.title, b.created_at,
                       COALESCE(
                           json_agg(
                               json_build_object('id', t.id, 'name', t.name, 'color', t.color)
                           ) FILTER (WHERE t.id IS NOT NULL),
                           '[]'
                       ) AS tags
                FROM books b
                LEFT JOIN book_tags bt ON bt.book_id = b.id
                LEFT JOIN tags t ON t.id = bt.tag_id
                WHERE b.title &@~ $1
                  AND ($2::int IS NULL OR EXISTS (
                      SELECT 1 FROM book_tags bt2
                      WHERE bt2.book_id = b.id AND bt2.tag_id = $2
                  ))
                GROUP BY b.id
                ORDER BY b.created_at DESC
                LIMIT 100
            """, q, tag_id)
        else:
            rows = await conn.fetch("""
                SELECT b.id, b.title, b.created_at,
                       COALESCE(
                           json_agg(
                               json_build_object('id', t.id, 'name', t.name, 'color', t.color)
                           ) FILTER (WHERE t.id IS NOT NULL),
                           '[]'
                       ) AS tags
                FROM books b
                LEFT JOIN book_tags bt ON bt.book_id = b.id
                LEFT JOIN tags t ON t.id = bt.tag_id
                WHERE ($1::int IS NULL OR EXISTS (
                    SELECT 1 FROM book_tags bt2
                    WHERE bt2.book_id = b.id AND bt2.tag_id = $1
                ))
                GROUP BY b.id
                ORDER BY b.created_at DESC
                LIMIT 100
            """, tag_id)

    import json
    books = []
    for row in rows:
        tags_raw = row["tags"]
        if isinstance(tags_raw, str):
            tags_data = json.loads(tags_raw)
        else:
            tags_data = tags_raw
        books.append({
            "id": row["id"],
            "title": row["title"],
            "created_at": row["created_at"].isoformat(),
            "tags": tags_data,
        })
    return JSONResponse(books)


@router.post("/api/books")
async def add_book(book: BookIn, user=Depends(require_user)):
    if not book.title.strip():
        raise HTTPException(400, "Title cannot be empty")
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "INSERT INTO books (title) VALUES ($1) RETURNING id, title, created_at",
                book.title.strip(),
            )
            book_id = row["id"]
            if book.tag_ids:
                await conn.executemany(
                    "INSERT INTO book_tags (book_id, tag_id) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    [(book_id, tid) for tid in book.tag_ids],
                )
            tags = await conn.fetch(
                "SELECT t.id, t.name, t.color FROM tags t JOIN book_tags bt ON bt.tag_id=t.id WHERE bt.book_id=$1",
                book_id,
            )
    return {
        "id": book_id,
        "title": row["title"],
        "created_at": row["created_at"].isoformat(),
        "tags": [dict(t) for t in tags],
    }


@router.put("/api/books/{book_id}")
async def update_book(book_id: int, book: BookUpdate, user=Depends(require_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        exists = await conn.fetchval("SELECT id FROM books WHERE id=$1", book_id)
        if not exists:
            raise HTTPException(404, "Book not found")
        async with conn.transaction():
            if book.title is not None:
                await conn.execute(
                    "UPDATE books SET title=$1, updated_at=NOW() WHERE id=$2",
                    book.title.strip(), book_id,
                )
            if book.tag_ids is not None:
                await conn.execute("DELETE FROM book_tags WHERE book_id=$1", book_id)
                if book.tag_ids:
                    await conn.executemany(
                        "INSERT INTO book_tags (book_id, tag_id) VALUES ($1, $2)",
                        [(book_id, tid) for tid in book.tag_ids],
                    )
            row = await conn.fetchrow("SELECT id, title, created_at FROM books WHERE id=$1", book_id)
            tags = await conn.fetch(
                "SELECT t.id, t.name, t.color FROM tags t JOIN book_tags bt ON bt.tag_id=t.id WHERE bt.book_id=$1",
                book_id,
            )
    return {
        "id": row["id"],
        "title": row["title"],
        "created_at": row["created_at"].isoformat(),
        "tags": [dict(t) for t in tags],
    }


@router.delete("/api/books/{book_id}")
async def delete_book(book_id: int, user=Depends(require_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        deleted = await conn.execute("DELETE FROM books WHERE id=$1", book_id)
    if deleted == "DELETE 0":
        raise HTTPException(404, "Book not found")
    return {"ok": True}


@router.get("/api/suggest")
async def suggest_titles(q: str = "", user=Depends(require_user)):
    """Proxy to Open Library search — returns title + author suggestions."""
    import httpx
    if len(q.strip()) < 2:
        return JSONResponse([])
    try:
        async with httpx.AsyncClient(timeout=4.0) as client:
            resp = await client.get(
                "https://openlibrary.org/search.json",
                params={"q": q, "fields": "title,author_name,first_publish_year", "limit": 8},
            )
        data = resp.json()
        results = []
        seen = set()
        for doc in data.get("docs", []):
            title = doc.get("title", "").strip()
            if not title or title.lower() in seen:
                continue
            seen.add(title.lower())
            authors = doc.get("author_name", [])
            year = doc.get("first_publish_year")
            results.append({
                "title": title,
                "author": authors[0] if authors else None,
                "year": year,
            })
        return JSONResponse(results)
    except Exception:
        return JSONResponse([])  # silently fail — suggestions are optional
