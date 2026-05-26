from dotenv import load_dotenv
load_dotenv()

import json
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional
from pydantic import BaseModel

import db
from ai_agent import run_warehouse_agent
from routers.transfer   import router as transfer_router
from routers.inbound    import router as inbound_router
from routers.outbound   import router as outbound_router
from routers.cycle_count import router as cycle_count_router
from routers.claims     import router as claims_router


class UTF8JSONResponse(JSONResponse):
    media_type = "application/json; charset=utf-8"
    def render(self, content) -> bytes:
        return json.dumps(content, ensure_ascii=False, default=str).encode("utf-8")


app = FastAPI(default_response_class=UTF8JSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Register Routers ──────────────────────────────────────────────────────────
app.include_router(transfer_router,    prefix="/api")
app.include_router(inbound_router,     prefix="/api")
app.include_router(outbound_router,    prefix="/api")
app.include_router(cycle_count_router, prefix="/api")
app.include_router(claims_router,      prefix="/api")


@app.on_event("startup")
def on_startup():
    db.ensure_ready()


# ── WMS Utility Endpoints ─────────────────────────────────────────────────────

@app.get("/api/warehouses")
def get_warehouses():
    with db.get_conn() as conn:
        rows = conn.execute("SELECT * FROM warehouses ORDER BY id").fetchall()
    return [dict(r) for r in rows]


@app.get("/api/products")
def get_products():
    with db.get_conn() as conn:
        rows = conn.execute("SELECT * FROM products ORDER BY sku").fetchall()
    return [dict(r) for r in rows]


@app.get("/api/inventory")
def get_inventory_summary(warehouse_id: str = None):
    """
    可用庫存彙總（PICKING + BUFFER AVAILABLE）。
    可選傳 warehouse_id 篩選單倉。
    """
    with db.get_conn() as conn:
        sql = """
            SELECT sl.warehouse_id, w.name AS warehouse_name,
                   i.sku, p.name AS product_name, p.unit,
                   SUM(i.quantity) AS quantity,
                   p.safety_stock
              FROM inventory i
              JOIN storage_locations sl ON i.location_id = sl.location_id
              JOIN warehouses w         ON sl.warehouse_id = w.id
              JOIN products p           ON i.sku = p.sku
             WHERE sl.zone_type IN ('PICKING','BUFFER')
               AND i.acct_status = 'AVAILABLE'
        """
        params = []
        if warehouse_id:
            sql += " AND sl.warehouse_id=%s"
            params.append(warehouse_id)
        sql += " GROUP BY sl.warehouse_id, w.name, i.sku, p.name, p.unit, p.safety_stock ORDER BY sl.warehouse_id, i.sku"
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/inventory/problem-stock")
def get_problem_stock(warehouse_id: str = None):
    """PROBLEM + COLLECT_BUFFER + DISUSE 的問題品庫存。"""
    with db.get_conn() as conn:
        sql = """
            SELECT sl.warehouse_id, w.name AS warehouse_name,
                   sl.zone_type, sl.cb_category,
                   i.sku, p.name AS product_name,
                   i.quantity, i.acct_status
              FROM inventory i
              JOIN storage_locations sl ON i.location_id = sl.location_id
              JOIN warehouses w         ON sl.warehouse_id = w.id
              JOIN products p           ON i.sku = p.sku
             WHERE sl.zone_type IN ('PROBLEM','COLLECT_BUFFER','DISUSE')
               AND i.quantity > 0
        """
        params = []
        if warehouse_id:
            sql += " AND sl.warehouse_id=%s"
            params.append(warehouse_id)
        sql += " ORDER BY sl.warehouse_id, sl.zone_type, i.sku"
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/dashboard")
def get_dashboard():
    """首頁儀表板數據：各倉庫概況 + 問題帳摘要 + 跨倉 Claim 摘要。"""
    with db.get_conn() as conn:
        warehouses = conn.execute("SELECT id, name FROM warehouses ORDER BY id").fetchall()

        wh_stats = []
        for wh in warehouses:
            wid = wh["id"]
            available = conn.execute("""
                SELECT SUM(i.quantity) AS total FROM inventory i
                  JOIN storage_locations sl ON i.location_id = sl.location_id
                 WHERE sl.warehouse_id=%s AND sl.zone_type IN ('PICKING','BUFFER')
                   AND i.acct_status='AVAILABLE'
            """, (wid,)).fetchone()["total"] or 0

            problem = conn.execute("""
                SELECT SUM(i.quantity) AS total FROM inventory i
                  JOIN storage_locations sl ON i.location_id = sl.location_id
                 WHERE sl.warehouse_id=%s AND sl.zone_type IN ('PROBLEM','COLLECT_BUFFER','DISUSE')
                   AND i.quantity > 0
            """, (wid,)).fetchone()["total"] or 0

            open_internal = conn.execute("""
                SELECT COUNT(*) AS n FROM claims
                 WHERE physical_wh=%s AND physical_wh=account_wh
                   AND status NOT IN ('RESOLVED','WRITTEN_OFF','REJECTED')
            """, (wid,)).fetchone()["n"]

            open_cross = conn.execute("""
                SELECT COUNT(*) AS n FROM claims
                 WHERE (physical_wh=%s OR account_wh=%s) AND physical_wh!=account_wh
                   AND status NOT IN ('RESOLVED','WRITTEN_OFF','REJECTED')
            """, (wid, wid)).fetchone()["n"]

            wh_stats.append({
                "warehouse_id": wid,
                "warehouse_name": wh["name"],
                "available_qty": available,
                "problem_qty": problem,
                "open_internal_claims": open_internal,
                "open_cross_claims": open_cross,
            })

        # 全局 Claim 統計
        claim_counts = conn.execute("""
            SELECT status, COUNT(*) AS n FROM claims GROUP BY status
        """).fetchall()
        claim_by_type = conn.execute("""
            SELECT claim_type, COUNT(*) AS n FROM claims GROUP BY claim_type
        """).fetchall()

        # 待處理作業數
        pending_inbound = conn.execute(
            "SELECT COUNT(*) AS n FROM inbound_orders WHERE status='DRAFT'"
        ).fetchone()["n"]
        pending_transfers = conn.execute(
            "SELECT COUNT(*) AS n FROM transfer_orders WHERE status IN ('DRAFT','IN_TRANSIT')"
        ).fetchone()["n"]
        pending_outbound = conn.execute(
            "SELECT COUNT(*) AS n FROM outbound_orders WHERE status='DRAFT'"
        ).fetchone()["n"]
        pending_counts = conn.execute(
            "SELECT COUNT(*) AS n FROM cycle_counts WHERE status='IN_PROGRESS'"
        ).fetchone()["n"]

    return {
        "warehouse_stats": wh_stats,
        "claim_summary": {
            "by_status": {r["status"]: r["n"] for r in claim_counts},
            "by_type":   {r["claim_type"]: r["n"] for r in claim_by_type},
        },
        "pending_operations": {
            "inbound":   pending_inbound,
            "transfers": pending_transfers,
            "outbound":  pending_outbound,
            "cycle_counts": pending_counts,
        },
    }


# ── AI Agent Endpoints ────────────────────────────────────────────────────────

class AgentChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None


@app.post("/agent/chat")
def agent_chat(body: AgentChatRequest):
    result = run_warehouse_agent(body.message, body.session_id)
    return result


@app.get("/agent/decision-log")
def decision_log_demo():
    result = run_warehouse_agent("給我全倉的異常摘要")
    return {"decision_log": result["decision_log"]}
