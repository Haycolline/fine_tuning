import unittest

from app.models import FAQ
from tests._harness import AppTestCase


class FAQApiTest(AppTestCase):
    def test_seed_data_is_loaded(self):
        resp = self.client.get("/api/faq")
        self.assertEqual(resp.status_code, 200)
        items = resp.json()
        self.assertEqual(len(items), 10)
        self.assertEqual(set(items[0]), {"id", "question", "answer", "category"})
        self.assertEqual(items[0]["question"], "会员怎么续费？")

    def test_seed_is_idempotent(self):
        """二次调用 seed_if_empty 不应该重复插入(重启服务很容易踩到)。"""
        from app.services import faq as faq_service

        db = self.session()
        faq_service.seed_if_empty(db)
        self.assertEqual(db.query(FAQ).count(), 10)

    def test_create_faq(self):
        payload = {"question": "支持投屏吗？", "answer": "支持，AirPlay 和 DLNA 均可。", "category": "播放"}
        resp = self.client.post("/api/faq", json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIsInstance(body["id"], int)
        self.assertEqual(body["question"], payload["question"])

        self.assertEqual(len(self.client.get("/api/faq").json()), 11)

    def test_create_faq_category_optional(self):
        resp = self.client.post("/api/faq", json={"question": "q", "answer": "a"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["category"], "")

    def test_create_faq_rejects_missing_field(self):
        resp = self.client.post("/api/faq", json={"question": "缺少答案"})
        self.assertEqual(resp.status_code, 422)

    def test_list_is_ordered_by_id(self):
        ids = [item["id"] for item in self.client.get("/api/faq").json()]
        self.assertEqual(ids, sorted(ids))


class KnowledgeGapTest(AppTestCase):
    """边界：这些是当前实现没有校验、上线后会咬人的地方。"""

    @unittest.expectedFailure
    def test_overlong_question_is_rejected(self):
        """question 列是 String(255)，但 schema 没有长度约束。

        SQLite 不校验长度所以这里"能写进去"，MySQL 严格模式下会 500。
        期望：schema 层就拦下来（422）。
        """
        resp = self.client.post("/api/faq", json={"question": "长" * 300, "answer": "a"})
        self.assertEqual(resp.status_code, 422)


if __name__ == "__main__":
    unittest.main()
