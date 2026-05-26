import db
from datetime import datetime, timedelta


def get_claim(claim_id: str) -> dict:
    with db.get_conn() as conn:
        row = conn.execute("""
            SELECT c.*,
                   wp.name AS physical_wh_name,
                   wa.name AS account_wh_name
              FROM claims c
              JOIN warehouses wp ON c.physical_wh = wp.id
              JOIN warehouses wa ON c.account_wh  = wa.id
             WHERE c.claim_id=%s
        """, (claim_id,)).fetchone()
    return dict(row) if row else {"error": f"找不到 {claim_id}"}


def list_claims(status: str = None, warehouse_id: str = None) -> list:
    with db.get_conn() as conn:
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
            sql += " AND c.status=%s"
            params.append(status)
        if warehouse_id:
            sql += " AND (c.physical_wh=%s OR c.account_wh=%s)"
            params.extend([warehouse_id, warehouse_id])
        sql += " ORDER BY c.created_at DESC"
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def get_duplicate_claims(sku: str, wh1: str, wh2: str, days: int = 7) -> dict:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    with db.get_conn() as conn:
        rows = conn.execute("""
            SELECT claim_id, claim_type, physical_wh, account_wh,
                   shortage_qty, excess_qty, status, created_at
              FROM claims
             WHERE (physical_wh=%s OR account_wh=%s)
               AND (physical_wh=%s OR account_wh=%s)
               AND created_at >= %s
             ORDER BY created_at DESC
        """, (wh1, wh1, wh2, wh2, cutoff)).fetchall()
    result = [dict(r) for r in rows]
    return {
        "sku": sku, "warehouses": [wh1, wh2], "days_checked": days,
        "count": len(result), "is_duplicate": len(result) > 1, "claims": result,
    }


def get_claim_summary() -> dict:
    with db.get_conn() as conn:
        rows = conn.execute("SELECT status, COUNT(*) AS count FROM claims GROUP BY status").fetchall()
        by_type = conn.execute("SELECT claim_type, COUNT(*) AS count FROM claims GROUP BY claim_type").fetchall()
    summary = {r["status"]: r["count"] for r in rows}
    summary["total"] = sum(summary.values())
    summary["by_type"] = {r["claim_type"]: r["count"] for r in by_type}
    return summary
