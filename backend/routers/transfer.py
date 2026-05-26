from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import uuid4
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import db

router = APIRouter(prefix="/transfers", tags=["transfers"])


# ── Pydantic Models ───────────────────────────────────────────────────────────

class TransferDetailIn(BaseModel):
    sku: str
    qty_ordered: int

class TransferCreate(BaseModel):
    from_wh: str
    to_wh: str
    ref_doc: Optional[str] = None
    created_by: str = "operator"
    details: List[TransferDetailIn]

class IssueDetailIn(BaseModel):
    detail_id: int
    qty_issued: int

class IssueRequest(BaseModel):
    details: List[IssueDetailIn]
    created_by: str = "operator"

class ReceiveDetailIn(BaseModel):
    detail_id: int
    qty_received: int

class ReceiveRequest(BaseModel):
    details: List[ReceiveDetailIn]
    created_by: str = "operator"


# ── ID Generators ─────────────────────────────────────────────────────────────

def _new_id(prefix: str) -> str:
    return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"

def _new_mvt_id() -> str:
    return f"MVT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def _new_claim_id() -> str:
    return f"CLM-{datetime.now().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"


# ── Inventory Helpers ─────────────────────────────────────────────────────────

def _deduct_inventory(conn, warehouse_id: str, sku: str, qty: int,
                      t_code: str, created_by: str) -> str:
    """
    PICKING 優先扣庫存，不足再扣 BUFFER。
    回傳最後一筆 movement_id（供 Claim trigger 使用）。
    """
    remaining = qty
    last_mvt = None

    for zone in ("PICKING", "BUFFER"):
        rows = conn.execute("""
            SELECT i.id, i.location_id, i.quantity
              FROM inventory i
              JOIN storage_locations sl ON i.location_id = sl.location_id
             WHERE sl.warehouse_id = %s AND sl.zone_type = %s
               AND i.sku = %s AND i.acct_status = 'AVAILABLE' AND i.quantity > 0
             ORDER BY i.quantity DESC
        """, (warehouse_id, zone, sku)).fetchall()

        for row in rows:
            if remaining <= 0:
                break
            take = min(row["quantity"], remaining)
            conn.execute(
                "UPDATE inventory SET quantity = quantity - %s, updated_at = %s WHERE id = %s",
                (take, datetime.now().isoformat(), row["id"])
            )
            mvt_id = _new_mvt_id()
            conn.execute("""
                INSERT INTO inventory_movements
                  (movement_id,movement_type,from_location,to_location,sku,quantity,t_code,created_by,created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (mvt_id, "TRANSFER_OUT", row["location_id"], None,
                  sku, take, t_code, created_by, datetime.now().isoformat()))
            last_mvt = mvt_id
            remaining -= take

        if remaining <= 0:
            break

    if remaining > 0:
        raise HTTPException(
            status_code=400,
            detail=f"[{warehouse_id}] {sku} 可用庫存不足，還差 {remaining} 個"
        )
    return last_mvt


def _add_inventory(conn, warehouse_id: str, sku: str, qty: int,
                   t_code: str, created_by: str) -> str:
    """收到的貨放入 BUFFER（第一個 BUFFER 儲位）。回傳 movement_id。"""
    buf = conn.execute(
        "SELECT location_id FROM storage_locations WHERE warehouse_id=%s AND zone_type='BUFFER' LIMIT 1",
        (warehouse_id,)
    ).fetchone()
    if not buf:
        raise HTTPException(status_code=500, detail=f"{warehouse_id} 找不到 BUFFER 儲位")

    to_loc = buf["location_id"]
    conn.execute("""
        INSERT INTO inventory(location_id,sku,quantity,acct_status,updated_at)
             VALUES (%s,%s,%s,'AVAILABLE',%s)
        ON CONFLICT(location_id,sku) DO UPDATE
             SET quantity = quantity + %s, updated_at = %s
    """, (to_loc, sku, qty, datetime.now().isoformat(),
          qty, datetime.now().isoformat()))

    mvt_id = _new_mvt_id()
    conn.execute("""
        INSERT INTO inventory_movements
          (movement_id,movement_type,from_location,to_location,sku,quantity,t_code,created_by,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (mvt_id, "TRANSFER_IN", None, to_loc,
          sku, qty, t_code, created_by, datetime.now().isoformat()))
    return mvt_id


# ── Auto Claim ────────────────────────────────────────────────────────────────

def _auto_shortage_claim(conn, order_id: str, from_wh: str, to_wh: str,
                         sku: str, shortage_qty: int, trigger_mvt: str) -> str:
    claim_id = _new_claim_id()
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO claims
          (claim_id,t_code,trigger_movement_id,claim_type,
           physical_wh,account_wh,initiated_by,responsible_party,
           shortage_qty,excess_qty,status,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (claim_id, order_id, trigger_mvt, "TRANSFER_SHORTAGE",
          to_wh, from_wh, to_wh, "ORIGIN_WH",
          shortage_qty, 0, "PENDING", now))

    conn.execute("""
        INSERT INTO claim_logs(claim_id,action,actor,note,timestamp)
        VALUES (%s,%s,%s,%s,%s)
    """, (claim_id, "系統自動建立", "system",
          f"調撥單 {order_id} {sku} 短少 {shortage_qty} 個，責任倉：{from_wh}", now))

    return claim_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_transfers(warehouse_id: Optional[str] = None, status: Optional[str] = None):
    with db.get_conn() as conn:
        sql = """
            SELECT t.*,
                   w1.name AS from_name, w1.location AS from_location,
                   w2.name AS to_name,   w2.location AS to_location
              FROM transfer_orders t
              JOIN warehouses w1 ON t.from_wh = w1.id
              JOIN warehouses w2 ON t.to_wh   = w2.id
             WHERE 1=1
        """
        params = []
        if warehouse_id:
            sql += " AND (t.from_wh=%s OR t.to_wh=%s)"
            params += [warehouse_id, warehouse_id]
        if status:
            sql += " AND t.status=%s"
            params.append(status)
        sql += " ORDER BY t.created_at DESC"
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


@router.get("/{order_id}")
def get_transfer(order_id: str):
    with db.get_conn() as conn:
        order = conn.execute("""
            SELECT t.*,
                   w1.name AS from_name, w2.name AS to_name
              FROM transfer_orders t
              JOIN warehouses w1 ON t.from_wh = w1.id
              JOIN warehouses w2 ON t.to_wh   = w2.id
             WHERE t.order_id = %s
        """, (order_id,)).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="調撥單不存在")

        details = conn.execute("""
            SELECT d.*, p.name AS product_name, p.unit
              FROM transfer_order_details d
              JOIN products p ON d.sku = p.sku
             WHERE d.order_id = %s
        """, (order_id,)).fetchall()

        claims = conn.execute("""
            SELECT c.*,
                   w1.name AS physical_wh_name,
                   w2.name AS account_wh_name
              FROM claims c
              JOIN warehouses w1 ON c.physical_wh = w1.id
              JOIN warehouses w2 ON c.account_wh  = w2.id
             WHERE c.t_code = %s
        """, (order_id,)).fetchall()

    return {
        "order":   dict(order),
        "details": [dict(d) for d in details],
        "claims":  [dict(c) for c in claims],
    }


@router.post("")
def create_transfer(body: TransferCreate):
    if body.from_wh == body.to_wh:
        raise HTTPException(status_code=400, detail="發貨倉與收貨倉不能相同")
    if not body.details:
        raise HTTPException(status_code=400, detail="至少填一個品項")

    with db.get_conn() as conn:
        for wh in (body.from_wh, body.to_wh):
            if not conn.execute("SELECT 1 FROM warehouses WHERE id=%s", (wh,)).fetchone():
                raise HTTPException(status_code=400, detail=f"倉庫 {wh} 不存在")

        order_id = _new_id("TRF")
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO transfer_orders(order_id,from_wh,to_wh,status,ref_doc,created_at,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (order_id, body.from_wh, body.to_wh, "DRAFT", body.ref_doc, now, body.created_by)
        )
        for d in body.details:
            if not conn.execute("SELECT 1 FROM products WHERE sku=%s", (d.sku,)).fetchone():
                raise HTTPException(status_code=400, detail=f"品項 {d.sku} 不存在")
            conn.execute(
                "INSERT INTO transfer_order_details(order_id,sku,qty_ordered) VALUES (%s,%s,%s)",
                (order_id, d.sku, d.qty_ordered)
            )
        conn.commit()
    return {"order_id": order_id, "status": "DRAFT"}


@router.post("/{order_id}/issue")
def issue_transfer(order_id: str, body: IssueRequest):
    """
    發貨倉確認出庫。
    狀態：DRAFT → IN_TRANSIT
    庫存：PICKING/BUFFER 扣除
    """
    with db.get_conn() as conn:
        order = conn.execute(
            "SELECT * FROM transfer_orders WHERE order_id=%s", (order_id,)
        ).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="調撥單不存在")
        if order["status"] != "DRAFT":
            raise HTTPException(status_code=400, detail=f"狀態 {order['status']} 無法執行出庫")

        for item in body.details:
            detail = conn.execute(
                "SELECT * FROM transfer_order_details WHERE id=%s AND order_id=%s",
                (item.detail_id, order_id)
            ).fetchone()
            if not detail:
                raise HTTPException(status_code=400, detail=f"明細 id={item.detail_id} 不存在")

            conn.execute(
                "UPDATE transfer_order_details SET qty_issued=%s WHERE id=%s",
                (item.qty_issued, item.detail_id)
            )
            _deduct_inventory(conn, order["from_wh"], detail["sku"],
                              item.qty_issued, order_id, body.created_by)

        conn.execute(
            "UPDATE transfer_orders SET status='IN_TRANSIT' WHERE order_id=%s", (order_id,)
        )
        conn.commit()
    return {"order_id": order_id, "status": "IN_TRANSIT"}


@router.post("/{order_id}/receive")
def receive_transfer(order_id: str, body: ReceiveRequest):
    """
    收貨倉確認到貨，加庫存，計算差異。
    狀態：IN_TRANSIT → RECEIVED

    差異處理：
      shortage > 0 → 自動建 TRANSFER_SHORTAGE Claim（account_wh = 發貨倉）
      excess > 0   → 加入庫存，回傳提示請手動建 TRANSFER_EXCESS Claim
    """
    with db.get_conn() as conn:
        order = conn.execute(
            "SELECT * FROM transfer_orders WHERE order_id=%s", (order_id,)
        ).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="調撥單不存在")
        if order["status"] != "IN_TRANSIT":
            raise HTTPException(status_code=400, detail=f"狀態 {order['status']} 無法執行收貨")

        auto_claims    = []
        excess_notices = []

        for item in body.details:
            detail = conn.execute(
                "SELECT * FROM transfer_order_details WHERE id=%s AND order_id=%s",
                (item.detail_id, order_id)
            ).fetchone()
            if not detail:
                raise HTTPException(status_code=400, detail=f"明細 id={item.detail_id} 不存在")

            issued   = detail["qty_issued"] or detail["qty_ordered"]
            received = item.qty_received
            shortage = max(0, issued - received)
            excess   = max(0, received - issued)

            conn.execute("""
                UPDATE transfer_order_details
                   SET qty_received=%s, shortage_qty=%s, excess_qty=%s
                 WHERE id=%s
            """, (received, shortage, excess, item.detail_id))

            mvt_id = _add_inventory(conn, order["to_wh"], detail["sku"],
                                    received, order_id, body.created_by)

            if shortage > 0:
                claim_id = _auto_shortage_claim(
                    conn, order_id,
                    order["from_wh"], order["to_wh"],
                    detail["sku"], shortage, mvt_id
                )
                auto_claims.append({
                    "sku": detail["sku"], "shortage": shortage,
                    "claim_id": claim_id,
                    "message": f"已自動建立 Claim，責任方：{order['from_wh']}"
                })

            if excess > 0:
                excess_notices.append({
                    "sku": detail["sku"], "excess": excess,
                    "message": "溢收，建議手動建立 TRANSFER_EXCESS Claim 通知發貨倉"
                })

        conn.execute(
            "UPDATE transfer_orders SET status='RECEIVED' WHERE order_id=%s", (order_id,)
        )
        conn.commit()

    return {
        "order_id":      order_id,
        "status":        "RECEIVED",
        "auto_claims":   auto_claims,
        "excess_notices": excess_notices,
    }


@router.post("/{order_id}/complete")
def complete_transfer(order_id: str):
    """
    RECEIVED → COMPLETED。
    有未結案的 Claim 會擋住結單。
    """
    with db.get_conn() as conn:
        order = conn.execute(
            "SELECT * FROM transfer_orders WHERE order_id=%s", (order_id,)
        ).fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="調撥單不存在")
        if order["status"] != "RECEIVED":
            raise HTTPException(status_code=400, detail=f"狀態 {order['status']} 無法結單")

        open_n = conn.execute("""
            SELECT COUNT(*) AS n FROM claims
             WHERE t_code=%s AND status NOT IN ('RESOLVED','WRITTEN_OFF','REJECTED')
        """, (order_id,)).fetchone()["n"]
        if open_n > 0:
            raise HTTPException(
                status_code=400,
                detail=f"尚有 {open_n} 筆未結案 Claim，請先處理再結單"
            )

        conn.execute(
            "UPDATE transfer_orders SET status='COMPLETED' WHERE order_id=%s", (order_id,)
        )
        conn.commit()
    return {"order_id": order_id, "status": "COMPLETED"}
