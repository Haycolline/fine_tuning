"""调用 DeepSeek/OpenAI 兼容 API 做 SFT 微调。

流程：校验 data/*.jsonl -> 上传 train/val -> 创建微调 job -> 轮询 -> 打印 fine_tuned_model id。

用法：
    .venv\\Scripts\\python scripts\\finetune.py --dry-run          # 只校验数据，不调 API
    .venv\\Scripts\\python scripts\\finetune.py                    # 真实提交微调

环境变量（复用 .env，微调端点单独可覆盖）：
    DEEPSEEK_API_KEY / DEEPSEEK_BASE_URL / DEEPSEEK_MODEL   来自 app/config.py
    FINE_TUNE_BASE_URL    微调 API base_url，默认同 DEEPSEEK_BASE_URL
    FINE_TUNE_MODEL       待微调基座模型 id，默认 settings.deepseek_model

说明：DeepSeek 的微调端点与 OpenAI 可能不一致，用 FINE_TUNE_BASE_URL 切换；脚本按
OpenAI 兼容接口（files / fine_tuning.jobs）编写，若云端只支持旧版 fine-tunes 接口，改
_client.fine_tuning 调用即可，其余流程不变。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from app.config import settings  # noqa: E402

DEFAULT_TRAIN = ROOT / "data" / "sft_train.jsonl"
DEFAULT_VAL = ROOT / "data" / "sft_val.jsonl"

TERMINAL_STATUS = {"succeeded", "failed", "cancelled"}


def validate(path: Path) -> int:
    """逐行校验 messages 结构，返回条数。不合法即抛异常。"""
    n = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            msgs = obj["messages"]
            if not msgs or msgs[0].get("role") != "system":
                raise ValueError(f"{path}: 首条 role 不是 system")
            if msgs[-1].get("role") != "assistant":
                raise ValueError(f"{path}: 末条 role 不是 assistant")
            json.loads(msgs[-1]["content"])  # assistant content 必须是 JSON 字符串
            n += 1
    if n == 0:
        raise ValueError(f"{path}: 无有效数据")
    return n


def build_client() -> OpenAI:
    base_url = os.getenv("FINE_TUNE_BASE_URL", settings.deepseek_base_url)
    api_key = settings.deepseek_api_key
    if not api_key:
        raise SystemExit("缺少 DEEPSEEK_API_KEY，请先配置 .env")
    return OpenAI(api_key=api_key, base_url=base_url)


def submit(client: OpenAI, model: str, train_id: str, val_id: str | None, suffix: str):
    kwargs: dict = {
        "model": model,
        "training_file": train_id,
        "suffix": suffix or None,
    }
    if val_id:
        kwargs["validation_file"] = val_id
    return client.fine_tuning.jobs.create(**kwargs)


def poll(client: OpenAI, job_id: str, interval: int = 30, timeout: int = 3600) -> str:
    """轮询到终态，返回 fine_tuned_model id（失败返回空串并报错）。"""
    start = time.time()
    while True:
        job = client.fine_tuning.jobs.retrieve(job_id)
        status = job.status
        print(f"[{status}] job={job_id}")
        if status in TERMINAL_STATUS:
            if status != "succeeded":
                raise SystemExit(f"微调失败：status={status}")
            model_id = getattr(job, "fine_tuned_model", None)
            if not model_id:
                raise SystemExit("微调成功但未返回 fine_tuned_model id")
            return model_id
        if time.time() - start > timeout:
            raise SystemExit(f"轮询超时（>{timeout}s），job 仍在 {status}")
        time.sleep(interval)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--train", default=str(DEFAULT_TRAIN))
    ap.add_argument("--val", default=str(DEFAULT_VAL))
    ap.add_argument("--model", default=None, help="基座模型 id，默认读 FINE_TUNE_MODEL 或 DEEPSEEK_MODEL")
    ap.add_argument("--suffix", default="audiobook-cs", help="微调模型名后缀")
    ap.add_argument("--dry-run", action="store_true", help="只校验数据不调 API")
    args = ap.parse_args()

    train_path, val_path = Path(args.train), Path(args.val)
    model = args.model or os.getenv("FINE_TUNE_MODEL", settings.deepseek_model)

    train_n = validate(train_path)
    val_n = validate(val_path)
    print(f"校验通过：train={train_n} 条, val={val_n} 条, 基座模型={model}")
    if args.dry_run:
        print("dry-run 结束，未调用 API。")
        return 0

    client = build_client()

    print("上传训练集...")
    train_file = client.files.create(
        file=open(train_path, "rb"),
        purpose="fine-tune",
    )
    print(f"训练集 file id: {train_file.id}")

    val_file = None
    if val_path.exists():
        print("上传验证集...")
        val_file = client.files.create(
            file=open(val_path, "rb"),
            purpose="fine-tune",
        )
        print(f"验证集 file id: {val_file.id}")

    job = submit(client, model, train_file.id, val_file.id if val_file else None, args.suffix)
    print(f"微调 job id: {job.id}")

    model_id = poll(client, job.id)
    print(f"\n完成。fine_tuned_model = {model_id}")
    print("把它写入 .env：DEEPSEEK_MODEL=<上面的 id>，推理时 app/services/llm.py 即用微调模型。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
