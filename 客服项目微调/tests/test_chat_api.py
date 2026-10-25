import unittest

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from tests._harness import AppTestCase
from app.main import app
from app.models import Conversation, Message


class ChatApiTest(AppTestCase):
    def _count(self, model) -> int:
        return self.session().scalar(select(func.count()).select_from(model))

    def test_new_conversation_returns_reply_and_id(self):
        resp = self.client.post("/api/chat", json={"message": "会员怎么续费？"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertEqual(body["reply"], self.fake_llm.reply)
        self.assertIsInstance(body["conversation_id"], int)
        self.assertEqual(self._count(Conversation), 1)

    def test_turn_is_persisted_with_both_roles(self):
        resp = self.client.post("/api/chat", json={"message": "怎么取消自动续费"})
        conv_id = resp.json()["conversation_id"]

        rows = self.session().scalars(
            select(Message).where(Message.conversation_id == conv_id).order_by(Message.id)
        ).all()
        self.assertEqual([m.role for m in rows], ["user", "assistant"])
        self.assertEqual(rows[0].content, "怎么取消自动续费")
        self.assertEqual(rows[1].content, self.fake_llm.reply)

    def test_continue_existing_conversation(self):
        first = self.client.post("/api/chat", json={"message": "会员有什么权益？"}).json()
        second = self.client.post(
            "/api/chat",
            json={"message": "那怎么取消自动续费？", "conversation_id": first["conversation_id"]},
        ).json()

        self.assertEqual(second["conversation_id"], first["conversation_id"])
        self.assertEqual(self._count(Conversation), 1)
        self.assertEqual(self._count(Message), 4)

    def test_unknown_conversation_id_is_created(self):
        """传一个不存在的 conversation_id，当前实现会直接建一条同 id 的会话。

        用户换设备/清缓存后很容易撞到这条分支。
        """
        resp = self.client.post("/api/chat", json={"message": "你好", "conversation_id": 999})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["conversation_id"], 999)
        self.assertIsNotNone(self.session().get(Conversation, 999))

    def test_missing_message_is_rejected(self):
        self.assertEqual(self.client.post("/api/chat", json={}).status_code, 422)

    def test_bad_conversation_id_type_is_rejected(self):
        resp = self.client.post("/api/chat", json={"message": "hi", "conversation_id": "abc"})
        self.assertEqual(resp.status_code, 422)

    def test_knowledge_base_is_injected_into_prompt(self):
        self.client.post("/api/chat", json={"message": "会员怎么续费？"})
        prompt = self.fake_llm.last_system_prompt
        self.assertIn("参考知识库", prompt)
        self.assertIn("会员中心", prompt)

    def test_llm_failure_is_handled_gracefully(self):
        """期望：LLM 挂了返回友好提示(200 或 503)，且不丢用户消息。

        现状：直接 500；且 user 消息没有 flush/commit，随会话一起回滚 —— 用户刚说的话丢了。
        """
        self.fake_llm.error = RuntimeError("deepseek timeout")
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.post("/api/chat", json={"message": "会员怎么续费？"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._count(Message), 2)

    def test_empty_message_is_rejected(self):
        """期望：空串/纯空白在 schema 层拦掉，别白烧一次 LLM 调用。"""
        resp = self.client.post("/api/chat", json={"message": "   "})
        self.assertEqual(resp.status_code, 422)

    def test_previous_turns_are_sent_to_llm(self):
        """期望：带 conversation_id 时把历史消息一并发给模型。

        现状：只发 system + 本轮 user；conversation 表只存不用，
        多轮追问("那怎么取消？")必然答歪。
        """
        first = self.client.post("/api/chat", json={"message": "会员怎么续费？"}).json()
        self.client.post(
            "/api/chat",
            json={"message": "那怎么取消？", "conversation_id": first["conversation_id"]},
        )
        self.assertEqual(len(self.fake_llm.calls[-1]), 3)


if __name__ == "__main__":
    unittest.main()
