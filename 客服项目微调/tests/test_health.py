import unittest

from tests._harness import AppTestCase


class HealthTest(AppTestCase):
    def test_health_ok(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"status": "ok"})

    def test_openapi_schema_loads(self):
        """能力发现：/docs、/openapi.json 能正常生成，说明路由/schema 没有冲突。"""
        resp = self.client.get("/openapi.json")
        self.assertEqual(resp.status_code, 200)
        paths = resp.json()["paths"]
        self.assertIn("/api/chat", paths)
        self.assertIn("/api/faq", paths)
        self.assertIn("/health", paths)


if __name__ == "__main__":
    unittest.main()
