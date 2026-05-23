from agent_db import get_conn
from tools.inventory_tools import compare_inventory


def suggest_transfer(sku: str, to_warehouse: str) -> dict:
    comparison = compare_inventory(sku)
    if "error" in comparison:
        return comparison

    all_wh = comparison["surplus_warehouses"] + comparison["deficit_warehouses"]
    target = next((w for w in all_wh if w["warehouse_id"] == to_warehouse), None)
    if not target:
        return {"error": f"找不到倉庫 {to_warehouse}"}

    candidates = [w for w in comparison["surplus_warehouses"] if w["warehouse_id"] != to_warehouse]
    if not candidates:
        return {
            "sku": sku, "to_warehouse": to_warehouse, "suggestion": None,
            "reason": "目前沒有其他倉庫有多餘庫存可供調撥",
            "deficit": abs(target.get("excess", 0)),
        }

    best = candidates[0]
    suggested_qty = min(best["excess"], abs(target.get("excess", best["excess"])))
    return {
        "sku": sku,
        "product_name": comparison["product_name"],
        "unit": comparison["unit"],
        "to_warehouse": to_warehouse,
        "to_warehouse_name": target["warehouse_name"],
        "to_warehouse_current_qty": target["quantity"],
        "to_warehouse_safety_stock": target["safety_stock"],
        "from_warehouse": best["warehouse_id"],
        "from_warehouse_name": best["warehouse_name"],
        "from_warehouse_current_qty": best["quantity"],
        "from_warehouse_excess": best["excess"],
        "suggested_qty": suggested_qty,
        "reason": (
            f"{best['warehouse_name']} 現有餘裕 {best['excess']} {comparison['unit']}，"
            f"建議調撥 {suggested_qty} {comparison['unit']} 至 {target['warehouse_name']}"
        ),
        "all_candidates": candidates,
    }


def get_transfer_history(sku: str) -> list:
    conn = get_conn()
    rows = conn.execute(
        """SELECT t.id, t.from_wh, wf.name as from_name,
                  t.to_wh, wt.name as to_name,
                  t.sku, t.qty, t.status, t.created_at
           FROM transfer_records t
           JOIN warehouses wf ON t.from_wh = wf.id
           JOIN warehouses wt ON t.to_wh = wt.id
           WHERE t.sku=? ORDER BY t.created_at DESC""",
        (sku,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def list_transfers(status: str = None, warehouse_id: str = None) -> list:
    conn = get_conn()
    sql = """
        SELECT t.id, t.from_wh, wf.name as from_name,
               t.to_wh, wt.name as to_name,
               t.sku, t.qty, t.status, t.created_at
        FROM transfer_records t
        JOIN warehouses wf ON t.from_wh = wf.id
        JOIN warehouses wt ON t.to_wh = wt.id
        WHERE 1=1
    """
    params = []
    if status:
        sql += " AND t.status=?"
        params.append(status)
    if warehouse_id:
        sql += " AND (t.from_wh=? OR t.to_wh=?)"
        params.extend([warehouse_id, warehouse_id])
    sql += " ORDER BY t.created_at DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
