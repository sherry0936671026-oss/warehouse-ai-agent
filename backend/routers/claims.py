from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import db

router = APIRouter(tags=["claims"])


# ── Pydantic Models ───────────────────────────────────────────────────────────

class ManualClaimCreate(BaseModel):
    """手動建立 Claim（用於 TRANSFER_EXCESS 溢收通知）。"""
    t_code: str
    claim_type: str          # 通常是 TRANSFER_EXCESS
    physical_wh: str
    account_wh: str
    initiated_by: str
    shortage_qty: int = 0
    excess_qty: int = 0
    note: str = ""
    created_by: str = "operator"

class ActionRequest(BaseModel):
    actor: str = "operator"
    note: str = ""

class MoveToCollectBufferRequest(BaseModel):
    """
    移入集貨緩衝區。
    cb_category 可選：SHORT | QUALITY | SPEC | COUNT | DAMAGE
    若不填，系統依 claim_type 自動推斷。
    """
    cb_category: Optional[str] = None
    actor: str = "operator"
    note: str = ""

class ResolveRequest(BaseModel):
    resolution: str          # COMPENSATED | ADJUSTED | RETURNED | ADJUSTED_INVENTORY
    actor: str = "operator"
    note: str = ""

class ApprovalActionRequest(BaseModel):
    actor: str = "operator"
    note: str = ""


# ── Status Transition Rules ───────────────────────────────────────────────────

CLAIM_TYPE_TO_CB = {
    "DAMAGE":             "DAMAGE",
    "COUNT_DISCREPANCY":  "COUNT",
    "INBOUND_SHORTAGE":   "SHORT",
    "PICKING_SHORTAGE":   "SHORT",
    "TRANSFER_SHORTAGE":  "SHORT",
    "TRANSFER_EXCESS":    "SHORT",
}

# 哪些 claim_type 有實體物品需要物理移動
PHYSICAL_CLAIM_TYPES = {"DAMAGE", "TRANSFER_EXCESS"}

VALID_NEXT = {
    "PENDING":           {"INVESTIGATING", "REJECTED"},
    "INVESTIGATING":     {"IN_COLLECT_BUFFER", "RESOLVED", "REJECTED"},
    "IN_COLLECT_BUFFER": {"DISUSE_PENDING", "RESOLVED", "REJECTED"},
    "DISUSE_PENDING":    set(),   # 只能透過 approval 異動
    "RESOLVED":          set(),
    "WRITTEN_OFF":       set(),
    "REJECTED":          set(),
}


# ── ID Generators ─────────────────────────────────────────────────────────────

def _new_claim_id(conn) -> str:
    d = datetime.now().strftime("%Y%m%d")
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM claims WHERE claim_id LIKE %s",
        (f"CLM-{d}-%",)
    ).fetchone()["n"]
    return f"CLM-{d}-{n+1:03d}"

def _new_mvt_id() -> str:
    return f"MVT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"

def _new_approval_id(conn) -> str:
    d = datetime.now().strftime("%Y%m%d")
    n = conn.execute(
        "SELECT COUNT(*) AS n FROM approvals WHERE approval_id LIKE %s",
        (f"APV-{d}-%",)
    ).fetchone()["n"]
    return f"APV-{d}-{n+1:03d}"


# ── Zone Move Helpers ─────────────────────────────────────────────────────────

def _get_inventory_in_zone(conn, warehouse_id: str, zone_type: str,
                            sku: str, cb_category: str = None) -> list:
    """取出某倉庫特定 zone 的品項庫存（用來確認有沒有實體物品可以移動）。"""
    sql = """
        SELECT i.id, i.location_id, i.quantity, i.acct_status
          FROM inventory i
          JOIN storage_locations sl ON i.location_id = sl.location_id
         WHERE sl.warehouse_id=%s AND sl.zone_type=%s AND i.sku=%s AND i.quantity>0
    """
    params = [warehouse_id, zone_type, sku]
    if cb_category:
        sql += " AND sl.cb_category=%s"
        params.append(cb_category)
    return conn.execute(sql, params).fetchall()


def _zone_move(conn, warehouse_id: str, sku: str,
               from_zone: str, to_zone: str,
               to_acct_status: str, t_code: str, actor: str,
               from_cb_cat: str = None, to_cb_cat: str = None) -> int:
    """
    將 sku 從 from_zone 全部移到 to_zone。
    回傳移動的總數量（0 表示沒有實體物品）。
    """
    src_rows = _get_inventory_in_zone(conn, warehouse_id, from_zone, sku, from_cb_cat)
    if not src_rows:
        return 0

    # 找目標儲位
    dst_loc = conn.execute("""
        SELECT location_id FROM storage_locations
         WHERE warehouse_id=%s AND zone_type=%s
           AND (cb_category=%s OR (%s IS NULL AND cb_category IS NULL))
         LIMIT 1
    """, (warehouse_id, to_zone, to_cb_cat, to_cb_cat)).fetchone()
    if not dst_loc:
        raise HTTPException(status_code=500,
            detail=f"{warehouse_id} 找不到目標儲位 {to_zone}/{to_cb_cat}")

    to_loc  = dst_loc["location_id"]
    total   = sum(r["quantity"] for r in src_rows)

    for row in src_rows:
        conn.execute("UPDATE inventory SET quantity=0, updated_at=%s WHERE id=%s",
                     (datetime.now().isoformat(), row["id"]))
        mvt_id = _new_mvt_id()
        conn.execute("""
            INSERT INTO inventory_movements
              (movement_id,movement_type,from_location,to_location,sku,quantity,t_code,created_by,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (mvt_id, "ZONE_MOVE", row["location_id"], to_loc,
              sku, row["quantity"], t_code, actor, datetime.now().isoformat()))

    conn.execute("""
        INSERT INTO inventory(location_id,sku,quantity,acct_status,updated_at)
             VALUES (%s,%s,%s,%s,%s)
        ON CONFLICT(location_id,sku) DO UPDATE
             SET quantity=quantity+%s, acct_status=%s, updated_at=%s
    """, (to_loc, sku, total, to_acct_status, datetime.now().isoformat(),
          total, to_acct_status, datetime.now().isoformat()))

    return total


def _writeoff_inventory(conn, warehouse_id: str, sku: str, actor: str, t_code: str):
    """DISUSE 區的品項正式除帳：acct_status → WRITTEN_OFF，quantity 歸零。"""
    rows = _get_inventory_in_zone(conn, warehouse_id, "DISUSE", sku)
    total = 0
    for row in rows:
        conn.execute("""
            UPDATE inventory SET quantity=0, acct_status='WRITTEN_OFF', updated_at=%s
             WHERE id=%s
        """, (datetime.now().isoformat(), row["id"]))
        mvt_id = _new_mvt_id()
        conn.execute("""
            INSERT INTO inventory_movements
              (movement_id,movement_type,from_location,to_location,sku,quantity,t_code,created_by,created_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (mvt_id, "WRITEOFF", row["location_id"], None,
              sku, row["quantity"], t_code, actor, datetime.now().isoformat()))
        total += row["quantity"]
    return total


# ── Log Helper ────────────────────────────────────────────────────────────────

def _log(conn, claim_id: str, action: str, actor: str, note: str = ""):
    conn.execute(
        "INSERT INTO claim_logs(claim_id,action,actor,note,timestamp) VALUES (%s,%s,%s,%s,%s)",
        (claim_id, action, actor, note, datetime.now().isoformat())
    )


# ── Endpoints: Claims ─────────────────────────────────────────────────────────

@router.get("/claims")
def list_claims(warehouse_id: Optional[str] = None,
                claim_type: Optional[str] = None,
                status: Optional[str] = None,
                cross_warehouse: Optional[bool] = None):
    """
    cross_warehouse=true  → 只顯示跨倉 Claim（TRANSFER_SHORTAGE / TRANSFER_EXCESS）
    cross_warehouse=false → 只顯示內部問題帳
    """
    conn = db.get_conn()
    sql = """
        SELECT c.*,
               wp.name AS physical_wh_name,
               wa.name AS account_wh_name
          FROM claims c
          JOIN warehouses wp ON c.physical_wh = wp.id
          JOIN warehouses wa ON c.account_wh  = wa.id
         WHERE 1=1
    """
    params = []
    if warehouse_id:
        sql += " AND (c.physical_wh=%s OR c.account_wh=%s)"
        params += [warehouse_id, warehouse_id]
    if claim_type:
        sql += " AND c.claim_type=%s"
        params.append(claim_type)
    if status:
        sql += " AND c.status=%s"
        params.append(status)
    if cross_warehouse is True:
        sql += " AND c.physical_wh != c.account_wh"
    elif cross_warehouse is False:
        sql += " AND c.physical_wh = c.account_wh"
    sql += " ORDER BY c.created_at DESC"

    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/claims/{claim_id}")
def get_claim(claim_id: str):
    conn = db.get_conn()
    claim = conn.execute("""
        SELECT c.*,
               wp.name AS physical_wh_name,
               wa.name AS account_wh_name
          FROM claims c
          JOIN warehouses wp ON c.physical_wh = wp.id
          JOIN warehouses wa ON c.account_wh  = wa.id
         WHERE c.claim_id=%s
    """, (claim_id,)).fetchone()
    if not claim:
        conn.close()
        raise HTTPException(status_code=404, detail="Claim 不存在")

    logs = conn.execute(
        "SELECT * FROM claim_logs WHERE claim_id=%s ORDER BY timestamp",
        (claim_id,)
    ).fetchall()

    # 若有關聯的 inventory movement，一併帶出
    movements = conn.execute("""
        SELECT * FROM inventory_movements
         WHERE t_code=%s OR movement_id=%s
         ORDER BY created_at
    """, (claim_id, claim["trigger_movement_id"] or "")).fetchall()

    conn.close()
    return {
        "claim":     dict(claim),
        "logs":      [dict(l) for l in logs],
        "movements": [dict(m) for m in movements],
    }


@router.post("/claims")
def create_claim_manual(body: ManualClaimCreate):
    """手動建立 Claim（主要用於 TRANSFER_EXCESS 溢收通知）。"""
    allowed = {"TRANSFER_EXCESS", "TRANSFER_SHORTAGE"}
    if body.claim_type not in allowed:
        raise HTTPException(status_code=400,
            detail=f"手動建立只允許：{allowed}，其他類型由作業自動觸發")

    conn = db.get_conn()
    for wh in (body.physical_wh, body.account_wh, body.initiated_by):
        if not conn.execute("SELECT 1 FROM warehouses WHERE id=%s", (wh,)).fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail=f"倉庫 {wh} 不存在")

    responsible = "ORIGIN_WH" if body.claim_type == "TRANSFER_SHORTAGE" else "DEST_WH"
    claim_id = _new_claim_id(conn)
    now = datetime.now().isoformat()

    conn.execute("""
        INSERT INTO claims
          (claim_id,t_code,trigger_movement_id,claim_type,
           physical_wh,account_wh,initiated_by,responsible_party,
           shortage_qty,excess_qty,status,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """, (claim_id, body.t_code, None, body.claim_type,
          body.physical_wh, body.account_wh, body.initiated_by, responsible,
          body.shortage_qty, body.excess_qty, "PENDING", now))
    _log(conn, claim_id, "手動建立", body.created_by, body.note)

    conn.commit()
    conn.close()
    return {"claim_id": claim_id, "status": "PENDING"}


# ── Claim Workflow Actions ────────────────────────────────────────────────────

@router.post("/claims/{claim_id}/investigate")
def investigate(claim_id: str, body: ActionRequest):
    """PENDING → INVESTIGATING"""
    conn = db.get_conn()
    claim = conn.execute("SELECT * FROM claims WHERE claim_id=%s", (claim_id,)).fetchone()
    if not claim:
        conn.close(); raise HTTPException(404, "Claim 不存在")
    if "INVESTIGATING" not in VALID_NEXT.get(claim["status"], set()):
        conn.close(); raise HTTPException(400, f"狀態 {claim['status']} 無法轉為 INVESTIGATING")

    conn.execute("UPDATE claims SET status='INVESTIGATING' WHERE claim_id=%s", (claim_id,))
    _log(conn, claim_id, "開始調查", body.actor, body.note)
    conn.commit(); conn.close()
    return {"claim_id": claim_id, "status": "INVESTIGATING"}


@router.post("/claims/{claim_id}/move-to-cb")
def move_to_collect_buffer(claim_id: str, body: MoveToCollectBufferRequest):
    """
    INVESTIGATING → IN_COLLECT_BUFFER

    有實體物品的 Claim（DAMAGE / TRANSFER_EXCESS）：
      → 物品從 PROBLEM 區移到對應的 COLLECT_BUFFER 子區（cb_category）

    無實體物品的 Claim（短少類）：
      → 僅更新狀態，記錄 log（物品不存在，不做物理移動）
    """
    conn = db.get_conn()
    claim = conn.execute("SELECT * FROM claims WHERE claim_id=%s", (claim_id,)).fetchone()
    if not claim:
        conn.close(); raise HTTPException(404, "Claim 不存在")
    if "IN_COLLECT_BUFFER" not in VALID_NEXT.get(claim["status"], set()):
        conn.close(); raise HTTPException(400, f"狀態 {claim['status']} 無法移至集貨緩衝")

    cb_cat = body.cb_category or CLAIM_TYPE_TO_CB.get(claim["claim_type"], "SHORT")

    # 驗證 cb_category 合法
    valid_cats = {"SHORT", "QUALITY", "SPEC", "COUNT", "DAMAGE"}
    if cb_cat not in valid_cats:
        conn.close(); raise HTTPException(400, f"cb_category 必須是 {valid_cats} 之一")

    moved_qty = 0
    if claim["claim_type"] in PHYSICAL_CLAIM_TYPES:
        # 找出關聯的 SKU（透過 trigger_movement_id）
        sku = None
        if claim["trigger_movement_id"]:
            mvt = conn.execute(
                "SELECT sku FROM inventory_movements WHERE movement_id=%s",
                (claim["trigger_movement_id"],)
            ).fetchone()
            sku = mvt["sku"] if mvt else None

        if sku:
            moved_qty = _zone_move(
                conn, claim["physical_wh"], sku,
                from_zone="PROBLEM", to_zone="COLLECT_BUFFER",
                to_acct_status="FROZEN", t_code=claim_id,
                actor=body.actor, to_cb_cat=cb_cat
            )

    conn.execute("UPDATE claims SET status='IN_COLLECT_BUFFER' WHERE claim_id=%s", (claim_id,))
    note = body.note or (
        f"物品已移入 CB-{cb_cat}（{moved_qty} 個）" if moved_qty
        else f"邏輯移至 CB-{cb_cat}（無實體物品）"
    )
    _log(conn, claim_id, f"移入集貨緩衝 CB-{cb_cat}", body.actor, note)
    conn.commit(); conn.close()
    return {"claim_id": claim_id, "status": "IN_COLLECT_BUFFER",
            "cb_category": cb_cat, "moved_qty": moved_qty}


@router.post("/claims/{claim_id}/move-to-disuse")
def move_to_disuse(claim_id: str, body: ActionRequest):
    """
    IN_COLLECT_BUFFER → DISUSE_PENDING

    有實體物品：COLLECT_BUFFER → DISUSE（PENDING_WRITEOFF）+ 建立審批單
    無實體物品：僅更新狀態 + 建立審批單
    """
    conn = db.get_conn()
    claim = conn.execute("SELECT * FROM claims WHERE claim_id=%s", (claim_id,)).fetchone()
    if not claim:
        conn.close(); raise HTTPException(404, "Claim 不存在")
    if "DISUSE_PENDING" not in VALID_NEXT.get(claim["status"], set()):
        conn.close(); raise HTTPException(400, f"狀態 {claim['status']} 無法移至廢棄品區")

    moved_qty = 0
    if claim["claim_type"] in PHYSICAL_CLAIM_TYPES:
        sku = None
        if claim["trigger_movement_id"]:
            mvt = conn.execute(
                "SELECT sku FROM inventory_movements WHERE movement_id=%s",
                (claim["trigger_movement_id"],)
            ).fetchone()
            sku = mvt["sku"] if mvt else None

        if sku:
            cb_cat = CLAIM_TYPE_TO_CB.get(claim["claim_type"], "SHORT")
            moved_qty = _zone_move(
                conn, claim["physical_wh"], sku,
                from_zone="COLLECT_BUFFER", to_zone="DISUSE",
                to_acct_status="PENDING_WRITEOFF", t_code=claim_id,
                actor=body.actor, from_cb_cat=cb_cat
            )

    # 建立審批單
    apv_id = _new_approval_id(conn)
    conn.execute("""
        INSERT INTO approvals(approval_id,ref_type,ref_id,status,note,created_at)
        VALUES (%s,%s,%s,%s,%s,%s)
    """, (apv_id, "WRITEOFF", claim_id, "PENDING",
          body.note or f"申請除帳 {moved_qty} 個", datetime.now().isoformat()))

    conn.execute("UPDATE claims SET status='DISUSE_PENDING' WHERE claim_id=%s", (claim_id,))
    _log(conn, claim_id, "申請除帳", body.actor,
         f"移入廢棄品區 {moved_qty} 個，審批單：{apv_id}")
    conn.commit(); conn.close()
    return {"claim_id": claim_id, "status": "DISUSE_PENDING", "approval_id": apv_id}


@router.post("/claims/{claim_id}/resolve")
def resolve_claim(claim_id: str, body: ResolveRequest):
    """
    → RESOLVED（適用所有狀態中非終態的 Claim）

    resolution 類型：
      COMPENSATED       對方補貨/轉帳已到位
      ADJUSTED          帳務調整（差異認可）
      RETURNED          物品退回
      ADJUSTED_INVENTORY 直接調整庫存（盤點差異）
    """
    conn = db.get_conn()
    claim = conn.execute("SELECT * FROM claims WHERE claim_id=%s", (claim_id,)).fetchone()
    if not claim:
        conn.close(); raise HTTPException(404, "Claim 不存在")
    if "RESOLVED" not in VALID_NEXT.get(claim["status"], set()):
        conn.close(); raise HTTPException(400, f"狀態 {claim['status']} 無法結案")

    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE claims SET status='RESOLVED', resolved_at=%s WHERE claim_id=%s",
        (now, claim_id)
    )
    _log(conn, claim_id, f"結案（{body.resolution}）", body.actor, body.note)
    conn.commit(); conn.close()
    return {"claim_id": claim_id, "status": "RESOLVED", "resolution": body.resolution}


@router.post("/claims/{claim_id}/reject")
def reject_claim(claim_id: str, body: ActionRequest):
    """→ REJECTED"""
    conn = db.get_conn()
    claim = conn.execute("SELECT * FROM claims WHERE claim_id=%s", (claim_id,)).fetchone()
    if not claim:
        conn.close(); raise HTTPException(404, "Claim 不存在")
    if "REJECTED" not in VALID_NEXT.get(claim["status"], set()):
        conn.close(); raise HTTPException(400, f"狀態 {claim['status']} 無法拒絕")

    conn.execute("UPDATE claims SET status='REJECTED' WHERE claim_id=%s", (claim_id,))
    _log(conn, claim_id, "拒絕", body.actor, body.note)
    conn.commit(); conn.close()
    return {"claim_id": claim_id, "status": "REJECTED"}


# ── Endpoints: Approvals ──────────────────────────────────────────────────────

@router.get("/approvals")
def list_approvals(status: Optional[str] = None):
    conn = db.get_conn()
    sql = """
        SELECT a.*,
               c.claim_type, c.physical_wh, c.shortage_qty,
               w.name AS warehouse_name
          FROM approvals a
          JOIN claims c ON a.ref_id = c.claim_id
          JOIN warehouses w ON c.physical_wh = w.id
         WHERE a.ref_type='WRITEOFF'
    """
    params = []
    if status:
        sql += " AND a.status=%s"
        params.append(status)
    sql += " ORDER BY a.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.post("/approvals/{approval_id}/approve")
def approve_writeoff(approval_id: str, body: ApprovalActionRequest):
    """
    核准除帳：
      1. approvals.status → APPROVED
      2. DISUSE 區庫存正式歸零（WRITTEN_OFF）
      3. claims.status → WRITTEN_OFF
    """
    conn = db.get_conn()
    apv = conn.execute(
        "SELECT * FROM approvals WHERE approval_id=%s", (approval_id,)
    ).fetchone()
    if not apv:
        conn.close(); raise HTTPException(404, "審批單不存在")
    if apv["status"] != "PENDING":
        conn.close(); raise HTTPException(400, f"審批狀態 {apv['status']} 無法核准")

    claim = conn.execute(
        "SELECT * FROM claims WHERE claim_id=%s", (apv["ref_id"],)
    ).fetchone()
    if not claim:
        conn.close(); raise HTTPException(404, "對應 Claim 不存在")

    now = datetime.now().isoformat()

    # 取得 SKU（透過 trigger_movement_id）
    sku = None
    if claim["trigger_movement_id"]:
        mvt = conn.execute(
            "SELECT sku FROM inventory_movements WHERE movement_id=%s",
            (claim["trigger_movement_id"],)
        ).fetchone()
        sku = mvt["sku"] if mvt else None

    written_off_qty = 0
    if sku:
        written_off_qty = _writeoff_inventory(
            conn, claim["physical_wh"], sku, body.actor, apv["ref_id"]
        )

    conn.execute("""
        UPDATE approvals SET status='APPROVED', approved_by=%s, approved_at=%s, note=%s
         WHERE approval_id=%s
    """, (body.actor, now, body.note, approval_id))

    conn.execute(
        "UPDATE claims SET status='WRITTEN_OFF', resolved_at=%s WHERE claim_id=%s",
        (now, apv["ref_id"])
    )
    _log(conn, apv["ref_id"], "核准除帳", body.actor,
         f"審批單 {approval_id} 核准，除帳 {written_off_qty} 個")

    conn.commit(); conn.close()
    return {
        "approval_id":    approval_id,
        "claim_id":       apv["ref_id"],
        "status":         "APPROVED",
        "written_off_qty": written_off_qty,
    }


@router.post("/approvals/{approval_id}/reject-approval")
def reject_approval(approval_id: str, body: ApprovalActionRequest):
    """
    拒絕除帳：
      1. approvals.status → REJECTED
      2. claims.status → IN_COLLECT_BUFFER（退回等待重新判定）
    """
    conn = db.get_conn()
    apv = conn.execute(
        "SELECT * FROM approvals WHERE approval_id=%s", (approval_id,)
    ).fetchone()
    if not apv:
        conn.close(); raise HTTPException(404, "審批單不存在")
    if apv["status"] != "PENDING":
        conn.close(); raise HTTPException(400, f"審批狀態 {apv['status']} 無法拒絕")

    now = datetime.now().isoformat()
    conn.execute("""
        UPDATE approvals SET status='REJECTED', approved_by=%s, approved_at=%s, note=%s
         WHERE approval_id=%s
    """, (body.actor, now, body.note, approval_id))
    conn.execute(
        "UPDATE claims SET status='IN_COLLECT_BUFFER' WHERE claim_id=%s",
        (apv["ref_id"],)
    )
    _log(conn, apv["ref_id"], "除帳申請被拒", body.actor,
         f"審批單 {approval_id} 拒絕，退回集貨緩衝區重新判定")

    conn.commit(); conn.close()
    return {"approval_id": approval_id, "status": "REJECTED",
            "claim_status": "IN_COLLECT_BUFFER"}
