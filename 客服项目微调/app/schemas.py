from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None

    @field_validator("message")
    @classmethod
    def _message_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message 不能为空")
        return v


class ChatResponse(BaseModel):
    reply: str
    conversation_id: int
    intent: list[str] = Field(default_factory=list)
    handoff: bool = False


class FAQItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    question: str
    answer: str
    category: str


class FAQCreate(BaseModel):
    question: str
    answer: str
    category: str = ""
