import db
from datetime import datetime, timedelta


def get_claim(claim_id: str) -> dict:
    conn = db.get_conn()
    row = conn.execute("""
        SELECT c.*,
               wp.name AS physical_wh_name,
               wa.name AS account_wh_name
          FROM claims c
          JOIN warehouses wp ON c.physical_wh = wp.id
          JOIN warehouses wa ON c.account_wh  = wa.id
         WHERE c.claim_id=?
    """, (claim_id,)).fetchone()
    conn.close()
    return dict(row) if row else {"error": f"找不到 {claim_id}"}


def list_claims(status: str = None, warehouse_id: str = None) -> list:
    conn = db.get_conn()
    sql = """
        SELECT c.claim_id, c.claim_type, c.t_code,
               c.physical_wh, wp.name AS physical_wh_name,
               c.account_wh,  wa.name AS account_wh_name,
               c.shortage_qty, c.excess_qty,
               c.status, c.created_at
          FROM claims c
          JOIN warehouses wp ON c.physical_wh = wp.id
          JOIN warehouses wa ON c.account_wh  = wa.id
         WHERE 1=1
    """
    params = []
    if status:
        sql += " AND c.status=?"
        params.append(status)
    if warehouse_id:
        sql += " AND (c.physical_wh=? OR c.account_wh=?)"
        params.extend([warehouse_id, warehouse_id])
    sql += " ORDER BY c.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_duplicate_claims(sku: str, wh1: str, wh2: str, days: int = 7) -> dict:
    conn = db.get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    rows = conn.execute("""
        SELECT claim_id, claim_type, physical_wh, account_wh,
               shortage_qty, excess_qty, status, created_at
          FROM claims
         WHERE (physical_wh=? OR account_wh=?)
           AND (physical_wh=? OR account_wh=?)
           AND created_at >= ?
         ORDER BY created_at DESC
    """, (wh1, wh1, wh2, wh2, cutoff)).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    return {
        "sku": sku, "warehouses": [wh1, wh2], "days_checked": days,
        "count": len(result), "is_duplicate": len(result) > 1, "claims": result,
    }


def get_claim_summary() -> dict:
    conn = db.get_conn()
    rows = conn.execute("SELECT status, COUNT(*) AS count FROM claims GROUP BY status").fetchall()
    by_type = conn.execute("SELECT claim_type, COUNT(*) AS count FROM claims GROUP BY claim_type").fetchall()
    conn.close()
    summary = {r["status"]: r["count"] for r in rows}
    summary["total"] = sum(summary.values())
    summary["by_type"] = {r["claim_type"]: r["count"] for r in by_type}
    return summary
