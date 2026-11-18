
from fastapi import APIRouter
from sqlalchemy import select

import models
from database import db_dependency
from schemas import CategoryOut

router = APIRouter(tags=["categories"])


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: db_dependency):
    return db.scalars(select(models.EventCategory).order_by(models.EventCategory.sort_order)).all()
