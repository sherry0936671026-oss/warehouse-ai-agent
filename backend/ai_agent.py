import os
import json
from typing import Optional
import anthropic
from harness import WarehouseHarness
from tools.inventory_tools import get_inventory, compare_inventory, check_safety_stock
from tools.claim_tools import get_claim, list_claims, get_duplicate_claims, get_claim_summary
from tools.transfer_tools import suggest_transfer, get_transfer_history, list_transfers
from tools.analytics_tools import get_kpi, get_anomalies

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"

# ── Tool 定義（給 Claude API 用）─────────────────────────────────────────────

INVENTORY_TOOLS = [
    {
        "name": "get_inventory",
        "description": "查詢某 SKU 在單倉或全倉的庫存數量及狀態",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {"type": "string", "description": "商品 SKU，如 P001"},
                "warehouse_id": {"type": "string", "description": "倉庫 ID（W1/W2/W3），不填則查全倉"},
            },
            "required": ["sku"],
        },
    },
    {
        "name": "compare_inventory",
        "description": "跨倉比較某 SKU 庫存，標示有餘裕和不足的倉庫",
        "input_schema": {
            "type": "object",
            "properties": {"sku": {"type": "string"}},
            "required": ["sku"],
        },
    },
    {
        "name": "check_safety_stock",
        "description": "找出低於安全庫存的品項，可指定倉庫或查全部",
        "input_schema": {
            "type": "object",
            "properties": {
                "warehouse_id": {"type": "string", "description": "倉庫 ID，不填則查全部"}
            },
        },
    },
]

CLAIM_TOOLS = [
    {
        "name": "get_claim",
        "description": "查詢單筆異議單的詳細資訊",
        "input_schema": {
            "type": "object",
            "properties": {"claim_id": {"type": "string", "description": "異議單 ID，如 CLM001"}},
            "required": ["claim_id"],
        },
    },
    {
        "name": "list_claims",
        "description": "列出異議單，可按狀態（PENDING/INVESTIGATING/RESOLVED 等）或倉庫篩選",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "warehouse_id": {"type": "string"},
            },
        },
    },
    {
        "name": "get_duplicate_claims",
        "description": "檢查同一對倉庫、同 SKU 在近期是否有重複異議單",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "wh1": {"type": "string"},
                "wh2": {"type": "string"},
                "days": {"type": "integer", "description": "檢查天數，預設 7"},
            },
            "required": ["sku", "wh1", "wh2"],
        },
    },
    {
        "name": "get_claim_summary",
        "description": "取得各狀態的異議單數量統計",
        "input_schema": {"type": "object", "properties": {}},
    },
]

TRANSFER_TOOLS = [
    {
        "name": "suggest_transfer",
        "description": "根據跨倉庫存分析，建議從哪個倉調撥多少數量到目標倉",
        "input_schema": {
            "type": "object",
            "properties": {
                "sku": {"type": "string"},
                "to_warehouse": {"type": "string", "description": "需要補貨的目標倉 ID"},
            },
            "required": ["sku", "to_warehouse"],
        },
    },
    {
        "name": "get_transfer_history",
        "description": "查詢某 SKU 的歷史調撥紀錄",
        "input_schema": {
            "type": "object",
            "properties": {"sku": {"type": "string"}},
            "required": ["sku"],
        },
    },
    {
        "name": "list_transfers",
        "description": "列出調撥紀錄，可按狀態或倉庫篩選",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string"},
                "warehouse_id": {"type": "string"},
            },
        },
    },
]

REPORT_TOOLS = [
    {
        "name": "get_kpi",
        "description": "取得某倉庫的 KPI 指標：claim 數、未結率、低庫存品項數",
        "input_schema": {
            "type": "object",
            "properties": {"warehouse_id": {"type": "string", "description": "倉庫 ID"}},
            "required": ["warehouse_id"],
        },
    },
    {
        "name": "get_anomalies",
        "description": "取得全倉異常摘要：低庫存警示 + 未結異議單 + 進行中調撥",
        "input_schema": {"type": "object", "properties": {}},
    },
]

TOOL_REGISTRY = {
    "get_inventory": get_inventory,
    "compare_inventory": compare_inventory,
    "check_safety_stock": check_safety_stock,
    "get_claim": get_claim,
    "list_claims": list_claims,
    "get_duplicate_claims": get_duplicate_claims,
    "get_claim_summary": get_claim_summary,
    "suggest_transfer": suggest_transfer,
    "get_transfer_history": get_transfer_history,
    "list_transfers": list_transfers,
    "get_kpi": get_kpi,
    "get_anomalies": get_anomalies,
}

# ── 對話歷史 ─────────────────────────────────────────────────────────────────
# key: session_id, value: list of {"role": "user"|"assistant", "content": str}
_sessions: dict[str, list[dict]] = {}
_MAX_HISTORY = 20  # 最多保留 10 輪對話


# ── 子 Agent 執行器────────────────────────────────────────────────────────────

def _run_sub_agent(system: str, tools: list, user_message: str,
                   harness: WarehouseHarness,
                   history: Optional[list] = None) -> str:
    """執行一個子 Agent，處理 tool use 迴圈，透過 harness 驗證每次工具呼叫。"""
    messages = list(history or []) + [{"role": "user", "content": user_message}]

    response = client.messages.create(
        model=MODEL, max_tokens=2048, system=system, tools=tools, messages=messages
    )

    while response.stop_reason == "tool_use":
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            fn = TOOL_REGISTRY.get(block.name)
            if fn:
                result = harness.call_tool(block.name, fn, **block.input)
            else:
                result = {"error": f"工具 {block.name} 不存在"}
                harness.add_reasoning("error", f"未知工具：{block.name}")
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False, default=str),
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})
        response = client.messages.create(
            model=MODEL, max_tokens=2048, system=system, tools=tools, messages=messages
        )

    return next((b.text for b in response.content if hasattr(b, "text")), "")


# ── Router ────────────────────────────────────────────────────────────────────

def _route(user_message: str) -> list[str]:
    response = client.messages.create(
        model=MODEL,
        max_tokens=30,
        system=(
            "你是路由器，判斷問題類別。只回答以下一個或多個（逗號分隔，不加空格）：\n"
            "inventory,claim,transfer,report\n"
            "規則：問庫存/安全庫存/低庫存=inventory；"
            "問異議單/claim/CLM=claim；"
            "問調撥/轉倉/補貨建議=transfer；"
            "問KPI/異常摘要/報告=report。"
        ),
        messages=[{"role": "user", "content": user_message}],
    )
    text = response.content[0].text.strip().lower()
    return [c.strip() for c in text.split(",") if c.strip() in {"inventory", "claim", "transfer", "report"}]


# ── 主入口 ────────────────────────────────────────────────────────────────────

def run_warehouse_agent(user_message: str, session_id: Optional[str] = None) -> dict:
    harness = WarehouseHarness()
    harness.add_reasoning("start", f"收到問題：{user_message}")

    # 取得對話歷史（純文字輪次，不含 tool_use blocks）
    history: list[dict] = []
    if session_id:
        history = list(_sessions.get(session_id, []))
        if history:
            harness.add_reasoning("history", f"載入 {len(history)//2} 輪對話歷史")

    categories = _route(user_message)
    if not categories:
        categories = ["report"]
    harness.add_reasoning("router", f"路由結果：{categories}")

    agent_configs = {
        "inventory": (
            "你是倉庫庫存 Agent，專門查詢庫存狀態和安全庫存。用繁體中文回答，數字要清楚。",
            INVENTORY_TOOLS,
        ),
        "claim": (
            "你是倉庫異議 Agent，專門查詢和分析異議單（claim）。用繁體中文回答，要說明異議原因和狀態。",
            CLAIM_TOOLS,
        ),
        "transfer": (
            "你是倉庫調撥 Agent，專門分析跨倉庫存並建議調撥方案。用繁體中文回答，要給出明確的從哪個倉調多少數量的建議。",
            TRANSFER_TOOLS,
        ),
        "report": (
            "你是倉庫報表 Agent，專門產出 KPI 分析和全倉異常摘要。用繁體中文回答，要有結構化的重點摘要。",
            REPORT_TOOLS,
        ),
    }

    results = {}
    for cat in categories:
        system, tools = agent_configs[cat]
        harness.add_reasoning("invoke", f"啟動 {cat} Agent")
        results[cat] = _run_sub_agent(system, tools, user_message, harness, history)

    if len(results) == 1:
        reply = list(results.values())[0]
        harness.add_reasoning("done", "單一 Agent 完成")
    else:
        context = "\n\n".join(f"【{k} Agent】\n{v}" for k, v in results.items())
        harness.add_reasoning("integrate", f"整合 {len(results)} 個子 Agent 結果")
        integrate_messages = list(history) + [{
            "role": "user",
            "content": f"使用者問題：{user_message}\n\n各 Agent 分析：\n{context}\n\n請整合以上資訊給出完整回答。",
        }]
        final = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system="你是倉庫總 Agent，整合多個子 Agent 的分析，給出完整且結構清晰的回答。用繁體中文。",
            messages=integrate_messages,
        )
        reply = final.content[0].text
        harness.add_reasoning("done", "整合完成")

    # 儲存對話歷史
    if session_id is not None:
        buf = _sessions.setdefault(session_id, [])
        buf.append({"role": "user", "content": user_message})
        buf.append({"role": "assistant", "content": reply})
        if len(buf) > _MAX_HISTORY:
            _sessions[session_id] = buf[-_MAX_HISTORY:]

    return {
        "reply": reply,
        "categories": categories,
        "decision_log": harness.get_decision_log(),
    }
