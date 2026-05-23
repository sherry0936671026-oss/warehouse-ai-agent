import db
from tools.inventory_tools import check_safety_stock
from tools.claim_tools import list_claims, get_claim_summary


def get_kpi(warehouse_id: str) -> dict:
    conn = db.get_conn()
    wh = conn.execute("SELECT * FROM warehouses WHERE id=?", (warehouse_id,)).fetchone()
    if not wh:
        conn.close()
        return {"error": f"找不到倉庫 {warehouse_id}"}

    total_claims = conn.execute(
        "SELECT COUNT(*) FROM claims WHERE physical_wh=? OR account_wh=?",
        (warehouse_id, warehouse_id)
    ).fetchone()[0]
    open_claims = conn.execute(
        """SELECT COUNT(*) FROM claims
            WHERE (physical_wh=? OR account_wh=?)
              AND status NOT IN ('RESOLVED','WRITTEN_OFF','REJECTED')""",
        (warehouse_id, warehouse_id)
    ).fetchone()[0]
    completed_transfers = conn.execute(
        "SELECT COUNT(*) FROM transfer_orders WHERE (from_wh=? OR to_wh=?) AND status='COMPLETED'",
        (warehouse_id, warehouse_id)
    ).fetchone()[0]
    conn.close()

    low_stock = check_safety_stock(warehouse_id)
    return {
        "warehouse_id": warehouse_id,
        "warehouse_name": wh["name"],
        "location": wh["location"],
        "total_claims": total_claims,
        "open_claims": open_claims,
        "claim_open_rate": round(open_claims / total_claims * 100, 1) if total_claims else 0.0,
        "completed_transfers": completed_transfers,
        "low_stock_count": len(low_stock),
        "low_stock_items": low_stock,
    }


def get_anomalies() -> dict:
    conn = db.get_conn()
    in_transit = conn.execute("""
        SELECT t.order_id, t.from_wh, wf.name AS from_name,
               t.to_wh, wt.name AS to_name,
               t.status, t.created_at
          FROM transfer_orders t
          JOIN warehouses wf ON t.from_wh = wf.id
          JOIN warehouses wt ON t.to_wh   = wt.id
         WHERE t.status NOT IN ('COMPLETED','CANCELLED')
         ORDER BY t.created_at
    """).fetchall()
    conn.close()

    low_stock = check_safety_stock()
    open_claims = list_claims(status="PENDING") + list_claims(status="INVESTIGATING")
    return {
        "low_stock_alerts": low_stock,
        "low_stock_count": len(low_stock),
        "open_claims": open_claims,
        "open_claims_count": len(open_claims),
        "claim_stats": get_claim_summary(),
        "in_transit_transfers": [dict(r) for r in in_transit],
        "in_transit_count": len(in_transit),
        "severity": (
            "高" if len(low_stock) >= 5 or len(open_claims) >= 8
            else "中" if len(low_stock) >= 3 or len(open_claims) >= 4
            else "低"
        ),
    }
