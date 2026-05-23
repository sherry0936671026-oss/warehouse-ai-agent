from agent_db import get_conn
from datetime import datetime, timedelta


def get_claim(claim_id: str) -> dict:
    conn = get_conn()
    row = conn.execute(
        """SELECT c.*, ws.name as source_name, wt.name as target_name
           FROM claims c
           JOIN warehouses ws ON c.source_wh = ws.id
           JOIN warehouses wt ON c.target_wh = wt.id
           WHERE c.id=?""",
        (claim_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else {"error": f"找不到 {claim_id}"}


def list_claims(status: str = None, warehouse_id: str = None) -> list:
    conn = get_conn()
    sql = """
        SELECT c.id, c.source_wh, ws.name as source_name,
               c.target_wh, wt.name as target_name,
               c.sku, c.qty, c.reason, c.status, c.created_at
        FROM claims c
        JOIN warehouses ws ON c.source_wh = ws.id
        JOIN warehouses wt ON c.target_wh = wt.id
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND c.status=?"
        params.append(status)
    if warehouse_id:
        sql += " AND (c.source_wh=? OR c.target_wh=?)"
        params.extend([warehouse_id, warehouse_id])
    sql += " ORDER BY c.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_duplicate_claims(sku: str, wh1: str, wh2: str, days: int = 7) -> dict:
    conn = get_conn()
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT id, source_wh, target_wh, sku, qty, reason, status, created_at
           FROM claims
           WHERE sku=?
             AND ((source_wh=? AND target_wh=?) OR (source_wh=? AND target_wh=?))
             AND created_at >= ?
           ORDER BY created_at DESC""",
        (sku, wh1, wh2, wh2, wh1, cutoff)
    ).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    return {
        "sku": sku, "warehouses": [wh1, wh2], "days_checked": days,
        "count": len(result), "is_duplicate": len(result) > 1, "claims": result,
    }


def get_claim_summary() -> dict:
    conn = get_conn()
    rows = conn.execute("SELECT status, COUNT(*) as count FROM claims GROUP BY status").fetchall()
    conn.close()
    summary = {r["status"]: r["count"] for r in rows}
    summary["total"] = sum(summary.values())
    return summary
