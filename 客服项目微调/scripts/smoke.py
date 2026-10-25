"""已启动服务的冒烟/回归脚本（真实 HTTP + 真实 MySQL + 真实 DeepSeek）。

先起服务：
    .venv\\Scripts\\python -m uvicorn app.main:app --port 8000

再跑：
    .venv\\Scripts\\python scripts\\smoke.py
    .venv\\Scripts\\python scripts\\smoke.py --base-url http://127.0.0.1:8000

单元测试(离线)只证明代码逻辑对；这个脚本证明"接线"对：库连得上、key 有余额、提示词能把知识库喂进模型。
"""

from __future__ import annotations

import argparse
import sys

import httpx

# (问题, 期望命中的关键词任一, 说明)  —— 关键词衰减到 0 就说明检索/提示词坏了
CASES: list[tuple[str, list[str], str]] = [
    ("会员怎么续费？", ["续费", "会员中心"], "会员问答"),
    ("怎么取消自动续费？", ["取消", "订阅", "自动续费"], "退订路径"),
    ("播放不了怎么办", ["网络", "缓存", "重试"], "故障排查"),
    ("一个账号能登录几台设备？", ["3 台", "3台", "三台"], "账号规则"),
    ("可以退款吗？", ["退款", "人工"], "售后边界"),
    ("今天会下雨吗？", ["人工", "听书", "不在"], "超范围应引导人工"),
]

results: list[tuple[bool, str, str]] = []


def check(ok: bool, name: str, detail: str = "") -> None:
    results.append((ok, name, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  <- {detail}" if detail else ""))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    base = args.base_url.rstrip("/")

    with httpx.Client(base_url=base, timeout=60.0) as c:
        # 1. 存活
        try:
            r = c.get("/health")
            check(r.status_code == 200 and r.json().get("status") == "ok", "GET /health", str(r.text[:200]))
        except httpx.HTTPError as exc:
            print(f"服务没起来或地址不对: {exc}")
            return 2

        # 2. 知识库已 seed
        r = c.get("/api/faq")
        faqs = r.json() if r.status_code == 200 else []
        check(len(faqs) >= 10, "GET /api/faq 种子数据已导入", f"count={len(faqs)}")

        # 3. 单轮问答质量
        for question, keywords, note in CASES:
            r = c.post("/api/chat", json={"message": question})
            if r.status_code != 200:
                check(False, f"POST /api/chat [{note}]", f"HTTP {r.status_code} {r.text[:300]}")
                continue
            reply = r.json().get("reply", "")
            hit = [k for k in keywords if k in reply]
            check(bool(hit), f"POST /api/chat [{note}]", f"q={question!r} reply={reply[:80]!r}")

        # 4. 多轮记忆：追问必须承接上文
        first = c.post("/api/chat", json={"message": "会员怎么续费？"}).json()
        conv_id = first.get("conversation_id")
        second = c.post("/api/chat", json={"message": "那取消的话呢？", "conversation_id": conv_id})
        body = second.json() if second.status_code == 200 else {}
        check(
            body.get("conversation_id") == conv_id and any(
                k in body.get("reply", "") for k in ("取消", "订阅", "续费")
            ),
            "多轮：同一个 conversation_id 承接上文",
            f"reply={body.get('reply', '')[:80]!r}",
        )

        # 5. 入参校验（当前实现会漏，先当文档用例跑）
        check(
            c.post("/api/chat", json={"message": "   "}).status_code == 422,
            "空 message 被拒（当前实现会放行，属已知缺陷）",
        )

    failed = [r for r in results if not r[0]]
    print(f"\n{len(results) - len(failed)}/{len(results)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
