from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import FAQ
from app.schemas import FAQCreate, FAQItem

router = APIRouter()


@router.get("/api/faq", response_model=list[FAQItem])
def list_faqs(db: Session = Depends(get_db)) -> list[FAQ]:
    return list(db.scalars(select(FAQ).order_by(FAQ.id)))


@router.post("/api/faq", response_model=FAQItem)
def create_faq(payload: FAQCreate, db: Session = Depends(get_db)) -> FAQ:
    faq = FAQ(**payload.model_dump())
    db.add(faq)
    db.commit()
    db.refresh(faq)
    return faq
