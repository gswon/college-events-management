from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

import models
from database import get_db
from schemas import CategoryOut

router = APIRouter(tags=["categories"])

db_dependency = Annotated[Session, Depends(get_db)]


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: db_dependency):
    return db.scalars(select(models.EventCategory).order_by(models.EventCategory.sort_order)).all()
