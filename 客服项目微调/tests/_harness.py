"""测试脚手架：把两个外部依赖(MySQL / DeepSeek)换成替身。

- 数据库 -> 进程内 SQLite(StaticPool 单连接)，不碰真实 MySQL
- LLM    -> FakeLLM，记录每次调用的 messages 并返回固定文本

这样测试可以离线、可重复、毫秒级跑完。
运行：python -m unittest discover -s tests -t .   （装了 pytest 也可直接 pytest）
"""

from __future__ import annotations

import os
import unittest
import warnings
from unittest import mock

# TestClient 的 portal 在不用 with 时会漏关流，刷一堆 ResourceWarning，与本项目无关
warnings.filterwarnings("ignore", category=ResourceWarning)

# 必须在 import app.* 之前设置：config.py 在导入时就会读取环境变量
os.environ["DEEPSEEK_API_KEY"] = "test-key"
os.environ["DATABASE_URL"] = "sqlite+pysqlite://"

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.database as database  # noqa: E402

# check_same_thread=False + StaticPool：SQLite 连接可以被 TestClient 的线程池复用
engine = create_engine(
    "sqlite+pysqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
database.engine = engine
database.SessionLocal.configure(bind=engine)

from fastapi.testclient import TestClient  # noqa: E402

import app.models  # noqa: E402,F401  注册 ORM 表，create_all 才有东西可建
from app.database import Base, SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.services import faq as faq_service  # noqa: E402


class FakeLLM:
    """假的 LLM 客户端：不发网络请求，同时把入参记录下来供断言。"""

    def __init__(self, reply: str = "好的，已为你处理。") -> None:
        self.reply = reply
        self.calls: list[list[dict[str, str]]] = []
        self.error: Exception | None = None

    def generate(self, messages: list[dict[str, str]]) -> str:
        self.calls.append(messages)
        if self.error is not None:
            raise self.error
        return self.reply

    @property
    def last_system_prompt(self) -> str:
        assert self.calls, "LLM 没有被调用过"
        return self.calls[-1][0]["content"]


class AppTestCase(unittest.TestCase):
    """每个用例都是干净的库 + 10 条种子 FAQ + 一个假 LLM。"""

    def setUp(self) -> None:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        self.fake_llm = FakeLLM()
        patcher = mock.patch("app.services.llm.generate", self.fake_llm.generate)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.client = TestClient(app)

        db = SessionLocal()
        try:
            faq_service.seed_if_empty(db)
        finally:
            db.close()

    def session(self):
        db = SessionLocal()
        self.addCleanup(db.close)
        return db
