# 听书智能客服

FastAPI + DeepSeek + MySQL 的听书领域智能客服后端。

## 启动步骤

1. 建库：

```sql
CREATE DATABASE audiobook_cs DEFAULT CHARACTER SET utf8mb4;
```

2. 配置环境变量：

```bash
cp .env.example .env
```

编辑 `.env`，填入 `DEEPSEEK_API_KEY` 和 `DATABASE_URL`。

3. 创建虚拟环境并安装依赖：

```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```

4. 启动：

```bash
.venv\Scripts\python -m uvicorn app.main:app --reload
```

启动时自动建表，并在 `faq` 表为空时导入听书领域种子数据。

## 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/health` | 健康检查 |
| POST | `/api/chat` | 客服对话，入参 `{"message": "...", "conversation_id": 1}` |
| GET  | `/api/faq` | FAQ 列表 |
| POST | `/api/faq` | 新增 FAQ |

对话示例：

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"会员怎么续费？"}'
```
