from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import db

router = APIRouter(prefix="/cycle-counts", tags=["cycle_counts"])


# ── Pydantic Models ───────────────────────────────────────────────────────────

class CycleCountCreate(BaseModel):
    warehouse_id: str
    count_type: str = "MANUAL"        # MANUAL | SCHEDULED
    location_id: Optional[str] = None # 指定儲位；None = 整倉 PICKING 層
    skus: Optional[List[str]] = None  # 指定品項；None = 該範圍所有品項
    created_by: str = "operator"

class SubmitDetailIn(BaseModel):
    detail_id: int
    qty_actual: int   # 實際盤點數量

class SubmitRequest(BaseModel):
    details: List[SubmitDetailIn]
    created_by: str = "operator"


# ── ID Generators ─────────────────────────────────────────────────────────────

def _new_count_id() -> str:
    d = datetime.now().strftime("%Y%m%d")
    conn = db.get_conn()
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM cycle_counts WHERE count_id LIKE %s",
        (f"CNT-{d}-%",)
    ).fetchone()["n"]
    conn.close()
    return f"CNT-{d}-{n+1:03d}"

def _new_mvt_id() -> str:
    return f"MVT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def _new_claim_id(conn) -> str:
    d = datetime.now().strftime("%Y%m%d")
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM claims WHERE claim_id LIKE %s",
        (f"CLM-{d}-%",)
    ).fetchone()["n"]
    return f"CLM-{d}-{n+1:03d}"


# ── Snapshot Helper ───────────────────────────────────────────────────────────

def _snapshot_inventory(conn, warehouse_id: str,
                         location_id: Optional[str],
                         skus: Optional[List[str]]) -> list:
    """
    取出當前庫存快照，作為盤點底稿的 qty_system。

    範圍規則：
      location_id 指定 → 只盤該儲位（任何 zone_type）
      location_id 未指定 → 盤整倉 PICKING + BUFFER（可用庫存層）
    """
    if location_id:
        sql = """
            SELECT i.location_id, i.sku, i.quantity AS qty_system
              FROM inventory i
             WHERE i.location_id = %s
               AND i.acct_status = 'AVAILABLE'
               AND i.quantity > 0
        """
        params: list = [location_id]
    else:
        sql = """
            SELECT i.location_id, i.sku, i.quantity AS qty_system
              FROM inventory i
              JOIN storage_locations sl ON i.location_id = sl.location_id
             WHERE sl.warehouse_id = %s
               AND sl.zone_type IN ('PICKING','BUFFER')
               AND i.acct_status = 'AVAILABLE'
               AND i.quantity > 0
        """
        params = [warehouse_id]

    if skus:
        placeholders = ",".join(["%s"] * len(skus))
        sql += f" AND i.sku IN ({placeholders})"
        params += skus

    return conn.execute(sql, params).fetchall()


# ── Inventory Adjustment ──────────────────────────────────────────────────────

def _apply_count_adj(conn, location_id: str, sku: str,
                     qty_system: int, qty_actual: int,
                     t_code: str, created_by: str) -> Optional[str]:
    """
    盤點調整：直接將庫存設為 qty_actual。
    記錄 COUNT_ADJ movement（delta != 0 才記）。
    回傳 movement_id 或 None。
    """
    delta = qty_actual - qty_system
    if delta == 0:
        return None

    conn.execute(
        "UPDATE inventory SET quantity=%s, updated_at=%s WHERE location_id=%s AND sku=%s",
        (qty_actual, datetime.now().isoformat(), location_id, sku)
    )

    # 若 qty_actual == 0 且 row 不存在，先 upsert
    conn.execute("""
        INSERT INTO inventory(location_id,sku,quantity,acct_status,updated_at)
             VALUES (%s,%s,%s,'AVAILABLE',%s)
        ON CONFLICT(location_id,sku) DO UPDATE
             SET quantity=%s, updated_at=%s
    """, (location_id, sku, qty_actual, datetime.now().isoformat(),
          qty_actual, datetime.now().isoformat()))

    mvt_id = _new_mvt_id()
    # 短少：from_location 有東西被扣掉；溢出：to_location 有東西加進來
    from_loc = location_id if delta < 0 else None
    to_loc   = location_id if delta > 0 else None
    conn.execute("""
        INSERT INTO inventory_movements
          (movement_id,movement_type,from_location,to_location,sku,quantity,t_code,created_by,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (mvt_id, "COUNT_ADJ", from_loc, to_loc,
          sku, abs(delta), t_code, created_by, datetime.now().isoformat()))
    return mvt_id


# ── Auto Claim ────────────────────────────────────────────────────────────────

def _auto_discrepancy_claim(conn, t_code: str, warehouse_id: str,
                             sku: str, shortage_qty: int,
                             trigger_mvt, location_id: str) -> str:
    """
    盤點短少 → COUNT_DISCREPANCY Claim（內部問題帳）。
    physical_wh = account_wh = 自己倉，responsible_party = SELF。
    """
    claim_id = _new_claim_id(conn)
    now = datetime.now().isoformat()
    conn.execute("""
        INSERT INTO claims
          (claim_id,t_code,trigger_movement_id,claim_type,
           physical_wh,account_wh,initiated_by,responsible_party,
           shortage_qty,excess_qty,status,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (claim_id, t_code, trigger_mvt, "COUNT_DISCREPANCY",
          warehouse_id, warehouse_id, warehouse_id, "SELF",
          shortage_qty, 0, "PENDING", now))
    conn.execute("""
        INSERT INTO claim_logs(claim_id,action,actor,note,timestamp)
        VALUES (%s,%s,%s,%s,%s)
    """, (claim_id, "系統自動建立", "system",
          f"盤點 {t_code}｜{location_id} {sku} 短少 {shortage_qty} 個", now))
    return claim_id


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("")
def list_cycle_counts(warehouse_id: Optional[str] = None,
                      status: Optional[str] = None):
    conn = db.get_conn()
    sql = """
        SELECT c.*, w.name AS warehouse_name,
               COUNT(d.id) AS detail_count,
               SUM(CASE WHEN d.difference < 0 THEN 1 ELSE 0 END) AS shortage_lines
          FROM cycle_counts c
          JOIN warehouses w ON c.warehouse_id = w.id
     LEFT JOIN cycle_count_details d ON c.count_id = d.count_id
         WHERE 1=1
    """
    params = []
    if warehouse_id:
        sql += " AND c.warehouse_id=%s"
        params.append(warehouse_id)
    if status:
        sql += " AND c.status=%s"
        params.append(status)
    sql += " GROUP BY c.count_id, w.name ORDER BY c.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/{count_id}")
def get_cycle_count(count_id: str):
    conn = db.get_conn()
    count = conn.execute("""
        SELECT c.*, w.name AS warehouse_name
          FROM cycle_counts c
          JOIN warehouses w ON c.warehouse_id = w.id
         WHERE c.count_id=%s
    """, (count_id,)).fetchone()
    if not count:
        conn.close()
        raise HTTPException(status_code=404, detail="盤點單不存在")

    details = conn.execute("""
        SELECT d.*,
               p.name AS product_name, p.unit,
               sl.label AS location_label, sl.zone_type
          FROM cycle_count_details d
          JOIN products p ON d.sku = p.sku
          JOIN storage_locations sl ON d.location_id = sl.location_id
         WHERE d.count_id=%s
         ORDER BY d.location_id, d.sku
    """, (count_id,)).fetchall()

    claims = conn.execute("""
        SELECT c.*, w.name AS warehouse_name
          FROM claims c
          JOIN warehouses w ON c.physical_wh = w.id
         WHERE c.t_code=%s
    """, (count_id,)).fetchall()

    conn.close()
    return {
        "count":   dict(count),
        "details": [dict(d) for d in details],
        "claims":  [dict(c) for c in claims],
    }


@router.post("")
def create_cycle_count(body: CycleCountCreate):
    """
    建立盤點單，自動快照當前庫存作為 qty_system。
    - location_id 指定 → 盤該儲位所有（或指定）SKU
    - 不指定 → 盤整倉 PICKING + BUFFER 層
    """
    conn = db.get_conn()
    if not conn.execute("SELECT 1 FROM warehouses WHERE id=%s", (body.warehouse_id,)).fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail=f"倉庫 {body.warehouse_id} 不存在")

    if body.location_id:
        loc = conn.execute(
            "SELECT * FROM storage_locations WHERE location_id=%s AND warehouse_id=%s",
            (body.location_id, body.warehouse_id)
        ).fetchone()
        if not loc:
            conn.close()
            raise HTTPException(status_code=400, detail=f"儲位 {body.location_id} 不存在或不屬於此倉庫")

    # 快照庫存
    rows = _snapshot_inventory(conn, body.warehouse_id, body.location_id, body.skus)
    if not rows:
        conn.close()
        raise HTTPException(status_code=400, detail="指定範圍內沒有可盤點的庫存")

    count_id = _new_count_id()
    now = datetime.now().isoformat()
    conn.execute(
        "INSERT INTO cycle_counts(count_id,warehouse_id,count_type,location_id,status,created_at,created_by) VALUES (%s,%s,%s,%s,%s,%s,%s)",
        (count_id, body.warehouse_id, body.count_type,
         body.location_id, "IN_PROGRESS", now, body.created_by)
    )
    for row in rows:
        conn.execute(
            "INSERT INTO cycle_count_details(count_id,location_id,sku,qty_system) VALUES (%s,%s,%s,%s)",
            (count_id, row["location_id"], row["sku"], row["qty_system"])
        )
    conn.commit()
    conn.close()
    return {
        "count_id":     count_id,
        "status":       "IN_PROGRESS",
        "detail_lines": len(rows),
        "message":      f"已建立 {len(rows)} 筆盤點項目，請填入實際數量後提交"
    }


@router.post("/{count_id}/submit")
def submit_cycle_count(count_id: str, body: SubmitRequest):
    """
    提交盤點結果。
    狀態：IN_PROGRESS → COMPLETED

    帳務處理：
      difference < 0（短少）→ 調減庫存 + 自動建 COUNT_DISCREPANCY Claim
      difference > 0（溢出）→ 調增庫存（帳務盈餘，不建 Claim）
      difference = 0        → 無異動
    """
    conn = db.get_conn()
    count = conn.execute(
        "SELECT * FROM cycle_counts WHERE count_id=%s", (count_id,)
    ).fetchone()
    if not count:
        conn.close()
        raise HTTPException(status_code=404, detail="盤點單不存在")
    if count["status"] != "IN_PROGRESS":
        conn.close()
        raise HTTPException(status_code=400, detail=f"狀態 {count['status']} 無法提交")

    auto_claims   = []
    surplus_lines = []
    clean_lines   = 0

    for item in body.details:
        if item.qty_actual < 0:
            conn.rollback(); conn.close()
            raise HTTPException(status_code=400, detail="實際數量不能為負數")

        detail = conn.execute(
            "SELECT * FROM cycle_count_details WHERE id=%s AND count_id=%s",
            (item.detail_id, count_id)
        ).fetchone()
        if not detail:
            conn.rollback(); conn.close()
            raise HTTPException(status_code=400, detail=f"明細 id={item.detail_id} 不存在")

        qty_system = detail["qty_system"]
        qty_actual = item.qty_actual
        difference = qty_actual - qty_system

        conn.execute(
            "UPDATE cycle_count_details SET qty_actual=%s, difference=%s WHERE id=%s",
            (qty_actual, difference, item.detail_id)
        )

        mvt_id = _apply_count_adj(
            conn, detail["location_id"], detail["sku"],
            qty_system, qty_actual, count_id, body.created_by
        )

        if difference < 0:
            claim_id = _auto_discrepancy_claim(
                conn, count_id, count["warehouse_id"],
                detail["sku"], abs(difference),
                mvt_id, detail["location_id"]
            )
            auto_claims.append({
                "sku":        detail["sku"],
                "location":   detail["location_id"],
                "difference": difference,
                "claim_id":   claim_id,
                "message":    f"短少 {abs(difference)} 個，已建立 COUNT_DISCREPANCY Claim"
            })
        elif difference > 0:
            surplus_lines.append({
                "sku":        detail["sku"],
                "location":   detail["location_id"],
                "difference": difference,
                "message":    f"盤點盈餘 {difference} 個，已調增庫存"
            })
        else:
            clean_lines += 1

    conn.execute(
        "UPDATE cycle_counts SET status='COMPLETED' WHERE count_id=%s", (count_id,)
    )
    conn.commit()
    conn.close()

    return {
        "count_id":     count_id,
        "status":       "COMPLETED",
        "clean_lines":  clean_lines,
        "auto_claims":  auto_claims,
        "surplus_lines": surplus_lines,
    }


@router.patch("/{count_id}/cancel")
def cancel_cycle_count(count_id: str):
    conn = db.get_conn()
    count = conn.execute(
        "SELECT status FROM cycle_counts WHERE count_id=%s", (count_id,)
    ).fetchone()
    if not count:
        conn.close()
        raise HTTPException(status_code=404, detail="盤點單不存在")
    if count["status"] == "COMPLETED":
        conn.close()
        raise HTTPException(status_code=400, detail="已完成的盤點單無法取消")

    conn.execute(
        "UPDATE cycle_counts SET status='CANCELLED' WHERE count_id=%s", (count_id,)
    )
    conn.commit()
    conn.close()
    return {"count_id": count_id, "status": "CANCELLED"}
