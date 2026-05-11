"""
Tags routes:
- GET  /api/tags        → list all tags
- POST /api/tags        → create tag (with color)
- PUT  /api/tags/{id}   → rename / recolor
- DELETE /api/tags/{id} → delete
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.database import get_pool
from app.auth import get_current_user, require_user

router = APIRouter()

# Predefined vibrant color palette for auto-assignment
TAG_COLORS = [
    "#ef4444", "#f97316", "#eab308", "#22c55e",
    "#06b6d4", "#3b82f6", "#8b5cf6", "#ec4899",
    "#14b8a6", "#f43f5e", "#84cc16", "#6366f1",
]


class TagIn(BaseModel):
    name: str
    color: str | None = None


class TagUpdate(BaseModel):
    name: str | None = None
    color: str | None = None


@router.get("/api/tags")
async def list_tags(user=Depends(require_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, name, color FROM tags ORDER BY name"
        )
    return [dict(r) for r in rows]


@router.post("/api/tags")
async def create_tag(tag: TagIn, user=Depends(require_user)):
    name = tag.name.strip().lower()
    if not name:
        raise HTTPException(400, "Tag name cannot be empty")

    # Auto-pick a color if not supplied
    pool = await get_pool()
    async with pool.acquire() as conn:
        count = await conn.fetchval("SELECT COUNT(*) FROM tags")
        color = tag.color or TAG_COLORS[int(count) % len(TAG_COLORS)]
        try:
            row = await conn.fetchrow(
                "INSERT INTO tags (name, color) VALUES ($1, $2) RETURNING id, name, color",
                name, color,
            )
        except Exception:
            raise HTTPException(409, "Tag already exists")
    return dict(row)


@router.put("/api/tags/{tag_id}")
async def update_tag(tag_id: int, tag: TagUpdate, user=Depends(require_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT id, name, color FROM tags WHERE id=$1", tag_id)
        if not row:
            raise HTTPException(404, "Tag not found")
        new_name = (tag.name or row["name"]).strip().lower()
        new_color = tag.color or row["color"]
        updated = await conn.fetchrow(
            "UPDATE tags SET name=$1, color=$2 WHERE id=$3 RETURNING id, name, color",
            new_name, new_color, tag_id,
        )
    return dict(updated)


@router.delete("/api/tags/{tag_id}")
async def delete_tag(tag_id: int, user=Depends(require_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM tags WHERE id=$1", tag_id)
    if result == "DELETE 0":
        raise HTTPException(404, "Tag not found")
    return {"ok": True}
