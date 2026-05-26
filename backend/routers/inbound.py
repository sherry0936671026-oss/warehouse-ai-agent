from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import db

router = APIRouter(prefix="/inbound", tags=["inbound"])


# ── Pydantic Models ───────────────────────────────────────────────────────────

class InboundDetailIn(BaseModel):
    sku: str
    qty_expected: int

class InboundCreate(BaseModel):
    warehouse_id: str
    supplier: str
    created_by: str = "operator"
    details: List[InboundDetailIn]

class ReceiveDetailIn(BaseModel):
    detail_id: int
    qty_actual: int       # 實際到貨總數（含損壞）
    damage_qty: int = 0   # 其中損壞幾個

class ReceiveRequest(BaseModel):
    details: List[ReceiveDetailIn]
    created_by: str = "operator"


# ── ID Generators ─────────────────────────────────────────────────────────────

def _new_inbound_id() -> str:
    return f"INB-{datetime.now().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"

def _new_mvt_id() -> str:
    return f"MVT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def _new_claim_id() -> str:
    return f"CLM-{datetime.now().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"


# ── Inventory Helpers ─────────────────────────────────────────────────────────

def _put_to_buffer(conn, warehouse_id: str, sku: str, qty: int,
                   t_code: str, created_by: str) -> str:
    """良品入 BUFFER（AVAILABLE）。"""
    loc = conn.execute(
        "SELECT location_id FROM storage_locations WHERE warehouse_id=%s AND zone_type='BUFFER' LIMIT 1",
        (warehouse_id,)
    ).fetchone()
    if not loc:
        raise HTTPException(status_code=500, detail=f"{warehouse_id} 找不到 BUFFER 儲位")

    to_loc = loc["location_id"]
    conn.execute("""
        INSERT INTO inventory(location_id,sku,quantity,acct_status,updated_at)
             VALUES (%s,%s,%s,'AVAILABLE',%s)
        ON CONFLICT(location_id,sku) DO UPDATE
             SET quantity=quantity+%s, updated_at=%s
    """, (to_loc, sku, qty, datetime.now().isoformat(),
          qty, datetime.now().isoformat()))

    mvt_id = _new_mvt_id()
    conn.execute("""
        INSERT INTO inventory_movements
          (movement_id,movement_type,from_location,to_location,sku,quantity,t_code,created_by,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (mvt_id, "INBOUND", None, to_loc,
          sku, qty, t_code, created_by, datetime.now().isoformat()))
    return mvt_id


def _put_to_problem(conn, warehouse_id: str, sku: str, qty: int,
                    t_code: str, created_by: str) -> str:
    """損壞品入 PROBLEM 區（FROZEN）。"""
    loc = conn.execute(
        "SELECT location_id FROM storage_locations WHERE warehouse_id=%s AND zone_type='PROBLEM' LIMIT 1",
        (warehouse_id,)
    ).fetchone()
    if not loc:
        raise HTTPException(status_code=500, detail=f"{warehouse_id} 找不到 PROBLEM 儲位")

    to_loc = loc["location_id"]
    conn.execute("""
        INSERT INTO inventory(location_id,sku,quantity,acct_status,updated_at)
             VALUES (%s,%s,%s,'FROZEN',%s)
        ON CONFLICT(location_id,sku) DO UPDATE
             SET quantity=quantity+%s, updated_at=%s
    """, (to_loc, sku, qty, datetime.now().isoformat(),
          qty, datetime.now().isoformat()))

    mvt_id = _new_mvt_id()
    conn.execute("""
        INSERT INTO inventory_movements
          (movement_id,movement_type,from_location,to_location,sku,quantity,t_code,created_by,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (mvt_id, "INBOUND", None, to_loc,
          sku, qty, t_code, created_by, datetime.now().isoformat()))
    return mvt_id


# ── Auto Claim ────────────────────────────────────────────────────────────────

def _auto_claim(conn, t_code: str, claim_type: str,
                warehouse_id: str, sku: str,
                shortage_qty: int, excess_qty: int,
                responsible_party: str, trigger_mvt,
                note: str) -> str:
    claim_id = _new_claim_id()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO claims
          (claim_id,t_code,trigger_movement_id,claim_type,
           physical_wh,account_wh,initiated_by,responsible_party,
           shortage_qty,excess_qty,status,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (claim_id, t_code, trigger_mvt, claim_type,
          warehouse_id, warehouse_id, warehouse_id, responsible_party,
          shortage_qty, excess_qty, "PENDING", now))

    conn.execute("""
        INSERT INTO claim_logs(claim_id,action,actor,note,timestamp)
        VALUES (%s,%s,%s,%s,%s)
    """, (claim_id, "系統自動建立", "system", note, now))

    return claim_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_inbound(warehouse_id: Optional[str] = None, status: Optional[str] = None):
    with db.get_conn() as conn:
        sql = """
            SELECT o.*, w.name AS warehouse_name
              FROM inbound_orders o
              JOIN warehouses w ON o.warehouse_id = w.id
             WHERE 1=1
        """
        params = []
        if warehouse_id:
            sql += " AND o.warehouse_id=%s"
            params.append(warehouse_id)
        if status:
            sql += " AND o.status=%s"
            params.append(status)
        sql += " ORDER BY o.created_at DESC"
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/{order_id}")
def get_inbound(order_id: str):
    with db.get_conn() as conn:
        order = conn.execute("""
            SELECT o.*, w.name AS warehouse_name
              FROM inbound_orders o
              JOIN warehouses w ON o.warehouse_id = w.id
             WHERE o.order_id=%s
        """, (order_id,)).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="入庫單不存在")

        details = conn.execute("""
            SELECT d.*, p.name AS product_name, p.unit
              FROM inbound_order_details d
              JOIN products p ON d.sku = p.sku
             WHERE d.order_id=%s
        """, (order_id,)).fetchall()

        claims = conn.execute("""
            SELECT c.*, w.name AS warehouse_name
              FROM claims c
              JOIN warehouses w ON c.physical_wh = w.id
             WHERE c.t_code=%s
        """, (order_id,)).fetchall()

    return {
        "order":   dict(order),
        "details": [dict(d) for d in details],
        "claims":  [dict(c) for c in claims],
    }


@router.post("")
def create_inbound(body: InboundCreate):
    if not body.details:
        raise HTTPException(status_code=400, detail="至少填一個品項")

    with db.get_conn() as conn:
        if not conn.execute("SELECT 1 FROM warehouses WHERE id=%s", (body.warehouse_id,)).fetchone():
            raise HTTPException(status_code=400, detail=f"倉庫 {body.warehouse_id} 不存在")

        order_id = _new_inbound_id()
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO inbound_orders(order_id,warehouse_id,supplier,status,created_at,created_by) VALUES (%s,%s,%s,%s,%s,%s)",
            (order_id, body.warehouse_id, body.supplier, "DRAFT", now, body.created_by)
        )
        for d in body.details:
            if not conn.execute("SELECT 1 FROM products WHERE sku=%s", (d.sku,)).fetchone():
                raise HTTPException(status_code=400, detail=f"品項 {d.sku} 不存在")
            conn.execute(
                "INSERT INTO inbound_order_details(order_id,sku,qty_expected) VALUES (%s,%s,%s)",
                (order_id, d.sku, d.qty_expected)
            )
        conn.commit()
    return {"order_id": order_id, "status": "DRAFT"}


@router.post("/{order_id}/receive")
def receive_inbound(order_id: str, body: ReceiveRequest):
    """
    執行入庫驗收。
    狀態：DRAFT → COMPLETED

    帳務處理：
      良品（qty_actual - damage_qty）→ BUFFER（AVAILABLE）
      損壞品（damage_qty）           → PROBLEM（FROZEN）+ 自動建 DAMAGE Claim
      短少（qty_expected - qty_actual > 0）→ 自動建 INBOUND_SHORTAGE Claim
      溢收（qty_actual > qty_expected）    → 正常入庫，紀錄在 excess_qty
    """
    with db.get_conn() as conn:
        order = conn.execute(
            "SELECT * FROM inbound_orders WHERE order_id=%s", (order_id,)
        ).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="入庫單不存在")
        if order["status"] not in ("DRAFT", "RECEIVING"):
            raise HTTPException(status_code=400, detail=f"狀態 {order['status']} 無法執行驗收")

        auto_claims    = []
        excess_notices = []

        for item in body.details:
            if item.damage_qty < 0 or item.qty_actual < 0:
                raise HTTPException(status_code=400, detail="數量不能為負數")
            if item.damage_qty > item.qty_actual:
                raise HTTPException(status_code=400, detail="損壞數量不能超過實際到貨數量")

            detail = conn.execute(
                "SELECT * FROM inbound_order_details WHERE id=%s AND order_id=%s",
                (item.detail_id, order_id)
            ).fetchone()
            if not detail:
                raise HTTPException(status_code=400, detail=f"明細 id={item.detail_id} 不存在")

            expected   = detail["qty_expected"]
            actual     = item.qty_actual
            damage     = item.damage_qty
            good       = actual - damage
            shortage   = max(0, expected - actual)
            excess     = max(0, actual - expected)

            conn.execute("""
                UPDATE inbound_order_details
                   SET qty_actual=%s, shortage_qty=%s, excess_qty=%s, damage_qty=%s
                 WHERE id=%s
            """, (actual, shortage, excess, damage, item.detail_id))

            if good > 0:
                _put_to_buffer(conn, order["warehouse_id"], detail["sku"],
                               good, order_id, body.created_by)

            if damage > 0:
                prob_mvt = _put_to_problem(conn, order["warehouse_id"], detail["sku"],
                                            damage, order_id, body.created_by)
                claim_id = _auto_claim(
                    conn, order_id, "DAMAGE",
                    order["warehouse_id"], detail["sku"],
                    damage, 0, "SUPPLIER", prob_mvt,
                    f"{order_id} {detail['sku']} 到貨損壞 {damage} 個，已移入問題品區"
                )
                auto_claims.append({
                    "sku": detail["sku"], "type": "DAMAGE",
                    "qty": damage, "claim_id": claim_id,
                    "message": f"損壞品已移入 PROBLEM 區，Claim 已建立"
                })

            if shortage > 0:
                claim_id = _auto_claim(
                    conn, order_id, "INBOUND_SHORTAGE",
                    order["warehouse_id"], detail["sku"],
                    shortage, 0, "SUPPLIER", None,
                    f"{order_id} {detail['sku']} 進貨短少 {shortage} 個，請聯繫供應商"
                )
                auto_claims.append({
                    "sku": detail["sku"], "type": "INBOUND_SHORTAGE",
                    "qty": shortage, "claim_id": claim_id,
                    "message": f"短少 {shortage} 個，已建立 Claim 責任方：SUPPLIER"
                })

            if excess > 0:
                excess_notices.append({
                    "sku": detail["sku"], "excess": excess,
                    "message": f"溢收 {excess} 個，已入庫，請確認是否需要退回供應商"
                })

        conn.execute(
            "UPDATE inbound_orders SET status='COMPLETED' WHERE order_id=%s", (order_id,)
        )
        conn.commit()

    return {
        "order_id":       order_id,
        "status":         "COMPLETED",
        "auto_claims":    auto_claims,
        "excess_notices": excess_notices,
    }


@router.patch("/{order_id}/cancel")
def cancel_inbound(order_id: str):
    with db.get_conn() as conn:
        order = conn.execute(
            "SELECT status FROM inbound_orders WHERE order_id=%s", (order_id,)
        ).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="入庫單不存在")
        if order["status"] == "COMPLETED":
            raise HTTPException(status_code=400, detail="已完成的入庫單無法取消")

        conn.execute(
            "UPDATE inbound_orders SET status='CANCELLED' WHERE order_id=%s", (order_id,)
        )
        conn.commit()
    return {"order_id": order_id, "status": "CANCELLED"}
