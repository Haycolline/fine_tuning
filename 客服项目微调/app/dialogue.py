"""客服对话结构化协议：意图/槽位/动作枚举、JSON 输出协议、系统提示词与少样本示例。

单一事实源：训练数据生成（data/）、微调提示词、运行时解析（app/services/chat.py）都从本模块取常量，
避免三处各写一份枚举漂移。
"""

from __future__ import annotations

# ---- 意图枚举（PRD §5 FR1）----
INTENTS: tuple[str, ...] = (
    "查询订单",
    "修改信息",
    "申请退款",
    "投诉升级",
    "人工转接",
    "FAQ 咨询",
    "超范围",
    "闲聊",
)

# ---- 槽位枚举（PRD §5 FR2）----
SLOTS: tuple[str, ...] = (
    "订单号",
    "手机号",
    "商品名",
    "时间",
    "地址",
    "金额",
    "问题类型",
)

# ---- 下一步动作（PRD §5 FR4 / §6）----
ACTIONS: tuple[str, ...] = (
    "collect_slot",
    "clarify",
    "execute",
    "handoff",
    "done",
)

# ---- 结构化输出协议（PRD §6）----
# 每轮模型输出一个 JSON 对象：
# {
#   "intent": ["FAQ 咨询"],            # 意图数组，可为空
#   "slots": {"订单号": "20250101001"}, # 槽位键值对，缺失槽位可不出现或为 null
#   "next_action": "execute",          # collect_slot / clarify / execute / handoff / done
#   "reply": "面向用户的中文回复",        # 唯一对外展示字段
#   "handoff": false                   # 是否转人工
# }

SYSTEM_PROMPT = (
    "你是「听书App」的智能客服。你的任务是识别用户意图、抽取槽位、在必要时澄清或转人工，并给出简洁、准确的中文回复。\n"
    "回答范围限于订阅、会员、播放、下载、账号、售后等听书相关问题。优先依据参考知识库回答，不要编造。知识库无法覆盖时，引导用户联系人工客服。\n"
    "\n"
    "你必须只输出一个 JSON 对象，不要输出任何解释或多余文本。JSON 字段如下：\n"
    "- intent: 字符串数组，从以下取值：查询订单、修改信息、申请退款、投诉升级、人工转接、FAQ 咨询、超范围、闲聊。可多选，无法识别时为空数组。\n"
    "- slots: 对象，可抽取的键为：订单号、手机号、商品名、时间、地址、金额、问题类型。没有抽取到的键不要出现。\n"
    "- next_action: 字符串，取值 collect_slot / clarify / execute / handoff / done。\n"
    "- reply: 面向用户的中文回复，3 句以内，专业、不编造。\n"
    "- handoff: 布尔值，是否需要转人工。\n"
    "\n"
    "规则：\n"
    "1. 槽位缺失或冲突时，next_action 用 clarify 或 collect_slot，reply 一次只问一个关键缺失项。\n"
    "2. 用户情绪升级、规则不可处理、信息冲突、流程无法继续时，next_action 用 handoff，handoff 为 true，不要错误承诺。\n"
    "3. 知识库覆盖的问题用 execute 直接回答；超出听书范围用 handoff 引导人工。"
)

# ---- 少样本示例（供数据生成与提示词复用）----
# 每条为 (用户消息, 期望 JSON)。反例在注释中标出。
FEW_SHOTS: tuple[tuple[str, str], ...] = (
    (
        "会员怎么续费？",
        '{"intent": ["FAQ 咨询"], "slots": {}, "next_action": "execute", "reply": "在「我的」-「会员中心」点击续费，支持微信、支付宝和 Apple 支付。", "handoff": false}',
    ),
    (
        "订单号 20250101001，钱扣了会员没到账",
        '{"intent": ["查询订单"], "slots": {"订单号": "20250101001", "问题类型": "充值未到账"}, "next_action": "collect_slot", "reply": "请提供您的手机号，我帮您进一步核实。", "handoff": false}',
    ),
    (
        "我要退款",
        '{"intent": ["申请退款"], "slots": {}, "next_action": "clarify", "reply": "请提供您的订单号，我帮您查询退款情况。", "handoff": false}',
    ),
    (
        "再解决不了我就去 12315 投诉你们",
        '{"intent": ["投诉升级"], "slots": {}, "next_action": "handoff", "reply": "非常抱歉给您带来不好的体验，我马上为您转接人工客服处理。", "handoff": true}',
    ),
    (
        "今天天气怎么样？",
        '{"intent": ["超范围"], "slots": {}, "next_action": "handoff", "reply": "这个问题超出我的服务范围，您可以联系人工客服咨询。", "handoff": true}',
    ),
)
