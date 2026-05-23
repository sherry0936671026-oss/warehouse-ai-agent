from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import db

router = APIRouter(prefix="/outbound", tags=["outbound"])


# ── Pydantic Models ───────────────────────────────────────────────────────────

class OutboundDetailIn(BaseModel):
    sku: str
    qty_ordered: int

class OutboundCreate(BaseModel):
    warehouse_id: str
    customer: str
    created_by: str = "operator"
    details: List[OutboundDetailIn]

class PickDetailIn(BaseModel):
    detail_id: int
    qty_picked: int       # 實際揀到的良品數（送出）
    damage_qty: int = 0   # 揀貨時發現損壞的數量

class PickRequest(BaseModel):
    details: List[PickDetailIn]
    created_by: str = "operator"


# ── ID Generators ─────────────────────────────────────────────────────────────

def _new_outbound_id() -> str:
    d = datetime.now().strftime("%Y%m%d")
    conn = db.get_conn()
    n = conn.execute(
        "SELECT COUNT(*) FROM outbound_orders WHERE order_id LIKE ?",
        (f"OUT-{d}-%",)
    ).fetchone()[0]
    conn.close()
    return f"OUT-{d}-{n+1:03d}"

def _new_mvt_id() -> str:
    return f"MVT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def _new_claim_id(conn) -> str:
    d = datetime.now().strftime("%Y%m%d")
    n = conn.execute(
        "SELECT COUNT(*) FROM claims WHERE claim_id LIKE ?",
        (f"CLM-{d}-%",)
    ).fetchone()[0]
    return f"CLM-{d}-{n+1:03d}"


# ── Inventory Helpers ─────────────────────────────────────────────────────────

def _deduct_picking(conn, warehouse_id: str, sku: str, qty: int,
                    movement_type: str, t_code: str, created_by: str) -> str:
    """
    從 PICKING 優先扣，不足扣 BUFFER。
    movement_type: OUTBOUND（出貨）或 ZONE_MOVE（移往問題區）
    回傳 movement_id（供 Claim trigger 使用）。
    """
    remaining = qty
    last_mvt  = None

    for zone in ("PICKING", "BUFFER"):
        rows = conn.execute("""
            SELECT i.id, i.location_id, i.quantity
              FROM inventory i
              JOIN storage_locations sl ON i.location_id = sl.location_id
             WHERE sl.warehouse_id=? AND sl.zone_type=?
               AND i.sku=? AND i.acct_status='AVAILABLE' AND i.quantity>0
             ORDER BY i.quantity DESC
        """, (warehouse_id, zone, sku)).fetchall()

        for row in rows:
            if remaining <= 0:
                break
            take = min(row["quantity"], remaining)
            conn.execute(
                "UPDATE inventory SET quantity=quantity-?, updated_at=? WHERE id=?",
                (take, datetime.now().isoformat(), row["id"])
            )
            mvt_id = _new_mvt_id()
            conn.execute("""
                INSERT INTO inventory_movements
                  (movement_id,movement_type,from_location,to_location,sku,quantity,t_code,created_by,created_at)
                VALUES (?,?,?,?,?,?,?,?,?)
            """, (mvt_id, movement_type, row["location_id"], None,
                  sku, take, t_code, created_by, datetime.now().isoformat()))
            last_mvt  = mvt_id
            remaining -= take

        if remaining <= 0:
            break

    if remaining > 0:
        raise HTTPException(
            status_code=400,
            detail=f"[{warehouse_id}] {sku} 可用庫存不足，還差 {remaining} 個"
        )
    return last_mvt


def _move_to_problem(conn, warehouse_id: str, sku: str, qty: int,
                     t_code: str, created_by: str) -> str:
    """損壞品從 PICKING/BUFFER 扣除，移入 PROBLEM（FROZEN）。"""
    # 先扣原位庫存（記錄 ZONE_MOVE）
    mvt_id = _deduct_picking(conn, warehouse_id, sku, qty, "ZONE_MOVE", t_code, created_by)

    # 加入 PROBLEM 區
    prob_loc = conn.execute(
        "SELECT location_id FROM storage_locations WHERE warehouse_id=? AND zone_type='PROBLEM' LIMIT 1",
        (warehouse_id,)
    ).fetchone()
    if not prob_loc:
        raise HTTPException(status_code=500, detail=f"{warehouse_id} 找不到 PROBLEM 儲位")

    to_loc = prob_loc["location_id"]
    conn.execute("""
        INSERT INTO inventory(location_id,sku,quantity,acct_status,updated_at)
             VALUES (?,?,?,'FROZEN',?)
        ON CONFLICT(location_id,sku) DO UPDATE
             SET quantity=quantity+?, updated_at=?
    """, (to_loc, sku, qty, datetime.now().isoformat(),
          qty, datetime.now().isoformat()))

    # 補一筆 ZONE_MOVE（進 PROBLEM 的那段）
    in_mvt = _new_mvt_id()
    conn.execute("""
        INSERT INTO inventory_movements
          (movement_id,movement_type,from_location,to_location,sku,quantity,t_code,created_by,created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (in_mvt, "ZONE_MOVE", None, to_loc,
          sku, qty, t_code, created_by, datetime.now().isoformat()))
    return mvt_id  # 回傳出庫那段的 mvt_id 作為 Claim trigger


# ── Auto Claim ────────────────────────────────────────────────────────────────

def _auto_claim(conn, t_code: str, claim_type: str,
                warehouse_id: str, sku: str,
                shortage_qty: int, responsible_party: str,
                trigger_mvt, note: str) -> str:
    claim_id = _new_claim_id(conn)
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO claims
          (claim_id,t_code,trigger_movement_id,claim_type,
           physical_wh,account_wh,initiated_by,responsible_party,
           shortage_qty,excess_qty,status,created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (claim_id, t_code, trigger_mvt, claim_type,
          warehouse_id, warehouse_id, warehouse_id, responsible_party,
          shortage_qty, 0, "PENDING", now))
    conn.execute("""
        INSERT INTO claim_logs(claim_id,action,actor,note,timestamp)
        VALUES (?,?,?,?,?)
    """, (claim_id, "系統自動建立", "system", note, now))
    return claim_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_outbound(warehouse_id: Optional[str] = None, status: Optional[str] = None):
    conn = db.get_conn()
    sql = """
        SELECT o.*, w.name AS warehouse_name
          FROM outbound_orders o
          JOIN warehouses w ON o.warehouse_id = w.id
         WHERE 1=1
    """
    params = []
    if warehouse_id:
        sql += " AND o.warehouse_id=?"
        params.append(warehouse_id)
    if status:
        sql += " AND o.status=?"
        params.append(status)
    sql += " ORDER BY o.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/{order_id}")
def get_outbound(order_id: str):
    conn = db.get_conn()
    order = conn.execute("""
        SELECT o.*, w.name AS warehouse_name
          FROM outbound_orders o
          JOIN warehouses w ON o.warehouse_id = w.id
         WHERE o.order_id=?
    """, (order_id,)).fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="出貨單不存在")

    details = conn.execute("""
        SELECT d.*, p.name AS product_name, p.unit
          FROM outbound_order_details d
          JOIN products p ON d.sku = p.sku
         WHERE d.order_id=?
    """, (order_id,)).fetchall()

    claims = conn.execute("""
        SELECT c.*, w.name AS warehouse_name
          FROM claims c
          JOIN warehouses w ON c.physical_wh = w.id
         WHERE c.t_code=?
    """, (order_id,)).fetchall()

    conn.close()
    return {
        "order":   dict(order),
        "details": [dict(d) for d in details],
        "claims":  [dict(c) for c in claims],
    }


@router.post("")
def create_outbound(body: OutboundCreate):
    if not body.details:
        raise HTTPException(status_code=400, detail="至少填一個品項")

    conn = db.get_conn()
    if not conn.execute("SELECT 1 FROM warehouses WHERE id=?", (body.warehouse_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"倉庫 {body.warehouse_id} 不存在")

    order_id = _new_outbound_id()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO outbound_orders(order_id,warehouse_id,customer,status,created_at,created_by) VALUES (?,?,?,?,?,?)",
        (order_id, body.warehouse_id, body.customer, "DRAFT", now, body.created_by)
    )
    for d in body.details:
        if not conn.execute("SELECT 1 FROM products WHERE sku=?", (d.sku,)).fetchone():
            conn.rollback(); conn.close()
            raise HTTPException(status_code=400, detail=f"品項 {d.sku} 不存在")
        conn.execute(
            "INSERT INTO outbound_order_details(order_id,sku,qty_ordered) VALUES (?,?,?)",
            (order_id, d.sku, d.qty_ordered)
        )
    conn.commit()
    conn.close()
    return {"order_id": order_id, "status": "DRAFT"}


@router.post("/{order_id}/pick")
def pick_outbound(order_id: str, body: PickRequest):
    """
    執行揀貨出庫。
    狀態：DRAFT → COMPLETED

    帳務處理：
      qty_picked   → PICKING/BUFFER 扣除（OUTBOUND）
      damage_qty   → PICKING/BUFFER 扣除後移入 PROBLEM（ZONE_MOVE）+ 自動建 DAMAGE Claim
      shortage_qty → 庫存不足（qty_ordered - qty_picked - damage_qty > 0）
                     → 自動建 PICKING_SHORTAGE Claim（帳務責任：自己倉）
    """
    conn = db.get_conn()
    order = conn.execute(
        "SELECT * FROM outbound_orders WHERE order_id=?", (order_id,)
    ).fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="出貨單不存在")
    if order["status"] not in ("DRAFT", "PICKING"):
        conn.close()
        raise HTTPException(status_code=400, detail=f"狀態 {order['status']} 無法執行揀貨")

    auto_claims = []

    for item in body.details:
        if item.qty_picked < 0 or item.damage_qty < 0:
            conn.rollback(); conn.close()
            raise HTTPException(status_code=400, detail="數量不能為負數")

        detail = conn.execute(
            "SELECT * FROM outbound_order_details WHERE id=? AND order_id=?",
            (item.detail_id, order_id)
        ).fetchone()
        if not detail:
            conn.rollback(); conn.close()
            raise HTTPException(status_code=400, detail=f"明細 id={item.detail_id} 不存在")

        ordered  = detail["qty_ordered"]
        picked   = item.qty_picked
        damage   = item.damage_qty
        shortage = max(0, ordered - picked - damage)

        conn.execute(
            "UPDATE outbound_order_details SET qty_picked=?, shortage_qty=? WHERE id=?",
            (picked, shortage, item.detail_id)
        )

        # 良品出庫：扣 PICKING/BUFFER
        if picked > 0:
            _deduct_picking(conn, order["warehouse_id"], detail["sku"],
                            picked, "OUTBOUND", order_id, body.created_by)

        # 損壞品：扣 PICKING/BUFFER → 移入 PROBLEM + 建 DAMAGE Claim
        if damage > 0:
            dmg_mvt = _move_to_problem(conn, order["warehouse_id"], detail["sku"],
                                       damage, order_id, body.created_by)
            claim_id = _auto_claim(
                conn, order_id, "DAMAGE",
                order["warehouse_id"], detail["sku"],
                damage, "SELF", dmg_mvt,
                f"{order_id} 揀貨時發現 {detail['sku']} 損壞 {damage} 個，已移入問題品區"
            )
            auto_claims.append({
                "sku": detail["sku"], "type": "DAMAGE",
                "qty": damage, "claim_id": claim_id,
                "message": "損壞品已移入 PROBLEM 區"
            })

        # 庫存短少：建 PICKING_SHORTAGE Claim
        if shortage > 0:
            claim_id = _auto_claim(
                conn, order_id, "PICKING_SHORTAGE",
                order["warehouse_id"], detail["sku"],
                shortage, "SELF", None,
                f"{order_id} 揀貨 {detail['sku']} 短少 {shortage} 個，帳務責任：自己倉"
            )
            auto_claims.append({
                "sku": detail["sku"], "type": "PICKING_SHORTAGE",
                "qty": shortage, "claim_id": claim_id,
                "message": f"揀貨短少 {shortage} 個，請盤點確認"
            })

    conn.execute(
        "UPDATE outbound_orders SET status='COMPLETED' WHERE order_id=?", (order_id,)
    )
    conn.commit()
    conn.close()

    return {
        "order_id":    order_id,
        "status":      "COMPLETED",
        "auto_claims": auto_claims,
    }


@router.patch("/{order_id}/cancel")
def cancel_outbound(order_id: str):
    conn = db.get_conn()
    order = conn.execute(
        "SELECT status FROM outbound_orders WHERE order_id=?", (order_id,)
    ).fetchone()
    if not order:
        conn.close()
        raise HTTPException(status_code=404, detail="出貨單不存在")
    if order["status"] == "COMPLETED":
        conn.close()
        raise HTTPException(status_code=400, detail="已完成的出貨單無法取消")

    conn.execute(
        "UPDATE outbound_orders SET status='CANCELLED' WHERE order_id=?", (order_id,)
    )
    conn.commit()
    conn.close()
    return {"order_id": order_id, "status": "CANCELLED"}
