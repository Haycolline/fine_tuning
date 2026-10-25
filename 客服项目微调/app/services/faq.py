from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FAQ
from app.seed_data import SEED_FAQS


def seed_if_empty(db: Session) -> None:
    if db.scalar(select(FAQ).limit(1)) is not None:
        return
    db.add_all([FAQ(**item) for item in SEED_FAQS])
    db.commit()


def search(db: Session, query: str, limit: int = 3) -> list[FAQ]:
    """按 2 字 bigram 重合度做关键词检索,返回 top-k FAQ。"""
    faqs = list(db.scalars(select(FAQ)).all())
    if not faqs:
        return []

    def score(faq: FAQ) -> int:
        text = faq.question + faq.answer
        bigrams = {query[i : i + 2] for i in range(len(query) - 1)}
        return sum(1 for bg in bigrams if bg in text)

    ranked = sorted(faqs, key=score, reverse=True)
    return [f for f in ranked if score(f) > 0][:limit]
