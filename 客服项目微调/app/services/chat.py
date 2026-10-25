import json
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.dialogue import SYSTEM_PROMPT
from app.models import Conversation, DialogueState, Message
from app.services import faq, llm

FALLBACK_REPLY = "抱歉，服务暂时不可用，请稍后再试。"


def _parse_reply(raw: str) -> dict:
    """把模型输出解析成 {reply, intent, handoff, next_action, slots}。

    模型应输出 §6 的 JSON；解析失败（纯文本、围栏包裹）时回退为纯文本 reply。
    """
    text = (raw or "").strip()
    data = None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group())
            except json.JSONDecodeError:
                data = None
    if not isinstance(data, dict):
        return {"reply": text or FALLBACK_REPLY, "intent": [], "handoff": False,
                "next_action": "", "slots": {}}

    intent = data.get("intent") or []
    if isinstance(intent, str):
        intent = [intent]
    slots = data.get("slots")
    if not isinstance(slots, dict):
        slots = {}
    return {
        "reply": data.get("reply") or text or FALLBACK_REPLY,
        "intent": intent,
        "handoff": bool(data.get("handoff", False)),
        "next_action": data.get("next_action") or "",
        "slots": slots,
    }


def _system_prompt(db: Session, message: str) -> str:
    context = faq.search(db, message)
    system = SYSTEM_PROMPT
    if context:
        lines = "\n".join(f"Q: {f.question}\nA: {f.answer}" for f in context)
        system += f"\n\n参考知识库:\n{lines}"
    return system


def _upsert_state(db: Session, conversation_id: int, parsed: dict) -> None:
    state = db.scalar(
        select(DialogueState).where(DialogueState.conversation_id == conversation_id)
    )
    if state is None:
        state = DialogueState(conversation_id=conversation_id)
        db.add(state)
    state.intent_json = json.dumps(parsed["intent"], ensure_ascii=False)
    state.slots_json = json.dumps(parsed["slots"], ensure_ascii=False)
    state.next_action = parsed["next_action"]


def handle_message(
    db: Session, message: str, conversation_id: int | None
) -> tuple[str, int, list[str], bool]:
    if conversation_id is not None:
        conv = db.get(Conversation, conversation_id)
        if conv is None:
            conv = Conversation(id=conversation_id)
            db.add(conv)
            db.flush()
    else:
        conv = Conversation()
        db.add(conv)
        db.flush()
        conversation_id = conv.id

    # 历史：本轮之前的 user 消息（喂给模型承接上下文）
    prior_user = list(
        db.scalars(
            select(Message.content)
            .where(Message.conversation_id == conversation_id, Message.role == "user")
            .order_by(Message.id)
        )
    )

    # 先落 user 消息，避免 LLM 异常时随回滚丢失
    db.add(Message(conversation_id=conversation_id, role="user", content=message))
    db.flush()

    messages = [{"role": "system", "content": _system_prompt(db, message)}]
    for content in prior_user:
        messages.append({"role": "user", "content": content})
    messages.append({"role": "user", "content": message})

    try:
        raw = llm.generate(messages)
    except Exception:
        parsed = {"reply": FALLBACK_REPLY, "intent": [], "handoff": False,
                  "next_action": "handoff", "slots": {}}
    else:
        parsed = _parse_reply(raw)

    db.add(Message(conversation_id=conversation_id, role="assistant", content=parsed["reply"]))
    _upsert_state(db, conversation_id, parsed)
    db.commit()

    return parsed["reply"], conversation_id, parsed["intent"], parsed["handoff"]
