from fastapi import APIRouter, Depends
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.db.session import get_db
from app.models.document import Document, DocumentStatus
from app.models.user import User
from app.schemas.admin import AdminUserSummary

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=list[AdminUserSummary])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[AdminUserSummary]:
    stmt = (
        select(
            User,
            func.count(Document.id).label("document_count"),
            func.sum(case((Document.status == DocumentStatus.DONE, 1), else_=0)).label("done_count"),
            func.sum(case((Document.status == DocumentStatus.ERROR, 1), else_=0)).label("error_count"),
        )
        .outerjoin(Document, Document.user_id == User.id)
        .group_by(User.id)
        .order_by(User.created_at.desc())
    )
    rows = (await db.execute(stmt)).all()

    return [
        AdminUserSummary(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_admin=user.is_admin,
            created_at=user.created_at,
            document_count=document_count,
            done_count=int(done_count or 0),
            error_count=int(error_count or 0),
        )
        for user, document_count, done_count, error_count in rows
    ]
