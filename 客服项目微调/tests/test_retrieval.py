import unittest

from app.services import faq as faq_service
from tests._harness import AppTestCase


class FAQSearchTest(AppTestCase):
    """检索层是全链路上最薄的一环：2-gram 重合度，没分词、没向量、每次全表扫。"""

    def test_hits_right_category_for_real_question(self):
        db = self.session()
        hits = faq_service.search(db, "会员怎么续费？")
        self.assertTrue(hits)
        self.assertLessEqual(len(hits), 3)
        self.assertIn("会员中心", hits[0].answer)

    def test_ranks_payment_question_first(self):
        db = self.session()
        self.assertEqual(faq_service.search(db, "怎么取消自动续费")[0].category, "会员")

    def test_irrelevant_query_returns_nothing(self):
        """不相关的问题不应该硬塞知识库，否则模型会被无关 FAQ 带偏。"""
        db = self.session()
        self.assertEqual(faq_service.search(db, "今天天气不错"), [])

    def test_limit_is_respected(self):
        db = self.session()
        self.assertLessEqual(len(faq_service.search(db, "会员下载播放账号退款", limit=1)), 1)

    def test_empty_table_is_safe(self):
        db = self.session()
        db.query(faq_service.FAQ).delete()
        db.commit()
        self.assertEqual(faq_service.search(db, "会员怎么续费"), [])

    @unittest.expectedFailure
    def test_single_char_query_still_matches(self):
        """单个汉字(如"退费"以外的一个字)算不出 bigram，检索直接返回空。

        现状：len(query) < 2 时 bigrams 为空集 -> 永远搜不到。
        """
        db = self.session()
        self.assertTrue(faq_service.search(db, "费"))

    @unittest.expectedFailure
    def test_english_only_query_matches(self):
        """bigram 是逐字子串匹配，英文词基本搜不到：查询 "APP" 的 bigram 是 {AP,PP}，
        而库里的文本写的是 "App"，大小写一差就 miss。中文客服里 "APP" 是高频词。"""
        db = self.session()
        self.assertTrue(faq_service.search(db, "APP"))


if __name__ == "__main__":
    unittest.main()
