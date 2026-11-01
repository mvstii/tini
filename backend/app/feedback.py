"""Uygulama içi geri bildirim (Faz 6): hata, öneri veya serbest not. Yalnızca kayıttır."""
from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.deps import current_user, get_db
from app.models import AppFeedback, User

router = APIRouter(prefix="/feedback", tags=["feedback"])


class FeedbackIn(BaseModel):
    kind: Literal["bug", "idea", "other"]
    screen: str = Field(max_length=64)
    app_version: str = Field(max_length=32)
    message: str = Field(min_length=3, max_length=2000)


@router.post("", status_code=201)
def send_feedback(
    body: FeedbackIn, user: User = Depends(current_user), db: Session = Depends(get_db)
) -> dict:
    row = AppFeedback(
        user_id=user.id, kind=body.kind, screen=body.screen,
        app_version=body.app_version, message=body.message.strip(),
    )
    db.add(row)
    db.commit()
    return {"id": row.id}
