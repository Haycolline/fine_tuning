from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import Base, SessionLocal, engine
from app.routers import chat, faq, health
from app.services import faq as faq_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        faq_service.seed_if_empty(db)
    finally:
        db.close()
    yield


app = FastAPI(title="听书智能客服", lifespan=lifespan)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(faq.router)
