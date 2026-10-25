# 听书智能客服 · 模型微调

FastAPI + DeepSeek + MySQL 的听书领域智能客服后端，含一套完整的模型微调（SFT）流水线。

目标：按 [项目实战.md](项目实战.md) 4.3 节，把客服模型在五类能力上微调并接入运行时——

- 4.3.1 意图识别（含多意图）
- 4.3.2 槽位抽取（含缺失/冲突识别）
- 4.3.3 澄清生成
- 4.3.4 多轮流程状态
- 4.3.5 异常与人工升级

模型统一输出结构化 JSON：`{"intent", "slots", "next_action", "reply", "handoff"}`。完整需求见 [docs/客服模型微调PRD.md](docs/客服模型微调PRD.md)。

## 目录结构

```
app/                   FastAPI 应用（models / schemas / routers / services）
app/dialogue.py        意图/槽位/动作枚举 + SYSTEM_PROMPT + 少样本（单一事实源）
app/services/llm.py    OpenAI 兼容 LLM 调用（model 可覆盖，微调后指到微调模型 id）
app/services/chat.py   运行时：知识库注入、历史喂入、§6 JSON 解析、对话状态落库
data/                  标注规范 + SFT 训练/验证集（OpenAI messages 格式）
scripts/gen_sft.py     从 app/dialogue.py 生成 SFT 数据
scripts/finetune.py    上传数据 → 建微调 job → 轮询 → 取 fine_tuned_model id
scripts/smoke.py       真机冒烟（需服务 + 真库 + 真 key）
eval/                  评测集 + 跑批脚本 + 打分表 + 验收报告
docs/                  PRD
tests/                 单元测试（离线：SQLite + FakeLLM）
```

## 快速开始

1. 建库：

```sql
CREATE DATABASE audiobook_cs DEFAULT CHARACTER SET utf8mb4;
```

2. 配置环境变量：

```bash
cp .env.example .env
```

编辑 `.env`，至少填 `DEEPSEEK_API_KEY` 和 `DATABASE_URL`。

3. 装依赖：

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
# 跑测试/评测再装开发依赖
.venv\Scripts\python -m pip install -r requirements-dev.txt
```

4. 启动：

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload
```

启动时自动建表，并在 `faq` 表为空时导入听书领域种子数据。

## 环境变量

| 变量                 | 默认值                                                      | 说明                                          |
| -------------------- | ----------------------------------------------------------- | --------------------------------------------- |
| `DATABASE_URL`       | `mysql+pymysql://root:password@127.0.0.1:3306/audiobook_cs` | MySQL 连接串                                  |
| `DEEPSEEK_API_KEY`   | 空                                                          | DeepSeek / OpenAI 兼容 key                    |
| `DEEPSEEK_BASE_URL`  | `https://api.deepseek.com`                                  | 推理 API base_url                             |
| `DEEPSEEK_MODEL`     | `deepseek-chat`                                             | 推理模型 id；微调后改成 `fine_tuned_model` id |
| `FINE_TUNE_BASE_URL` | 同 `DEEPSEEK_BASE_URL`                                      | 微调 API base_url（可选覆盖）                 |
| `FINE_TUNE_MODEL`    | 同 `DEEPSEEK_MODEL`                                         | 微调基座模型 id（可选覆盖）                   |

## 接口

| 方法 | 路径        | 说明     |
| ---- | ----------- | -------- |
| GET  | `/health`   | 健康检查 |
| POST | `/api/chat` | 客服对话 |
| GET  | `/api/faq`  | FAQ 列表 |
| POST | `/api/faq`  | 新增 FAQ |

`POST /api/chat` 入参 `{"message": "...", "conversation_id": 1}`（`conversation_id` 可省，首次自动建会话）。返回：

```json
{
  "reply": "在「我的」-「会员中心」点击续费即可。",
  "conversation_id": 1,
  "intent": ["FAQ 咨询"],
  "handoff": false
}
```

对话示例：

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"会员怎么续费？"}'
```

## 模型微调流程

```
1. app/dialogue.py            定义协议（枚举 + SYSTEM_PROMPT + 少样本）
2. scripts/gen_sft.py         生成 data/sft_train.jsonl / sft_val.jsonl
3. scripts/finetune.py        提交 DeepSeek/OpenAI 兼容 SFT，取 fine_tuned_model id
4. .env 里 DEEPSEEK_MODEL=<id>  推理自动走微调模型
```

```bash
.venv\Scripts\python scripts\gen_sft.py
.venv\Scripts\python scripts\finetune.py --dry-run   # 只校验数据不调 API
.venv\Scripts\python scripts\finetune.py             # 真实提交（需 key + 云端额度）
```

微调端点与 OpenAI 不一致时用 `FINE_TUNE_BASE_URL` 切换；脚本按 OpenAI 兼容接口（`files` / `fine_tuning.jobs`）编写。数据格式与标注规则见 [data/标注规范.md](data/标注规范.md)。

## 测试

离线单元测试（SQLite + FakeLLM，无需真库/真 key）：

```bash
python -m unittest discover -s tests -t .
```

真机冒烟（先起服务，验证库、key、知识库注入、多轮记忆）：

```bash
.venv\Scripts\python -m uvicorn app.main:app --port 8000
.venv\Scripts\python scripts\smoke.py
```

## 评测与验收

先起服务，再跑评测集（关键词初筛 + intent/handoff 结构化对比，落到 `eval/result.csv`）：

```bash
.venv\Scripts\python eval\run_eval.py
.venv\Scripts\python eval\run_eval.py --only 意图
```

人工按 [eval/打分表.md](eval/打分表.md) 打 D1–D5，对照 [eval/验收报告.md](eval/验收报告.md) 的 Go/No-Go 三项门槛（编造率 0、`handoff=true` 100% 给人工入口、加权总分 ≥85%）。

## 相关文档

- [docs/客服模型微调PRD.md](docs/客服模型微调PRD.md) —— 需求与验收标准
- [data/标注规范.md](data/标注规范.md) —— SFT 标注规则
- [eval/验收报告.md](eval/验收报告.md) —— M4 验收
