from agent_db import get_conn


def get_inventory(sku: str, warehouse_id: str = None) -> dict:
    conn = get_conn()
    c = conn.cursor()
    if warehouse_id:
        row = c.execute(
            """SELECT i.warehouse_id, w.name as warehouse_name, i.sku, i.product_name,
                      i.quantity, i.safety_stock, i.unit
               FROM inventory i JOIN warehouses w ON i.warehouse_id = w.id
               WHERE i.sku=? AND i.warehouse_id=?""",
            (sku, warehouse_id)
        ).fetchone()
        conn.close()
        if not row:
            return {"error": f"找不到 {sku} 在 {warehouse_id} 的庫存"}
        d = dict(row)
        d["status"] = "低庫存" if d["quantity"] < d["safety_stock"] else "正常"
        d["shortage"] = max(0, d["safety_stock"] - d["quantity"])
        return d

    rows = c.execute(
        """SELECT i.warehouse_id, w.name as warehouse_name, i.sku, i.product_name,
                  i.quantity, i.safety_stock, i.unit
           FROM inventory i JOIN warehouses w ON i.warehouse_id = w.id
           WHERE i.sku=? ORDER BY i.quantity DESC""",
        (sku,)
    ).fetchall()
    conn.close()
    if not rows:
        return {"error": f"找不到 SKU {sku}"}
    warehouses, total = [], 0
    for r in rows:
        d = dict(r)
        d["status"] = "低庫存" if d["quantity"] < d["safety_stock"] else "正常"
        d["shortage"] = max(0, d["safety_stock"] - d["quantity"])
        warehouses.append(d)
        total += d["quantity"]
    return {
        "sku": sku,
        "product_name": rows[0]["product_name"],
        "unit": rows[0]["unit"],
        "total_quantity": total,
        "warehouses": warehouses,
    }


def compare_inventory(sku: str) -> dict:
    result = get_inventory(sku)
    if "error" in result:
        return result
    surplus, deficit = [], []
    for wh in result["warehouses"]:
        wh["excess"] = wh["quantity"] - wh["safety_stock"]
        (surplus if wh["excess"] > 0 else deficit).append(wh)
    surplus.sort(key=lambda x: x["excess"], reverse=True)
    deficit.sort(key=lambda x: x["excess"])
    return {
        "sku": sku,
        "product_name": result["product_name"],
        "unit": result["unit"],
        "total_quantity": result["total_quantity"],
        "surplus_warehouses": surplus,
        "deficit_warehouses": deficit,
        "transferable": len(surplus) > 0 and len(deficit) > 0,
    }


def check_safety_stock(warehouse_id: str = None) -> list:
    conn = get_conn()
    sql = """
        SELECT i.warehouse_id, w.name as warehouse_name, i.sku, i.product_name,
               i.quantity, i.safety_stock, i.unit,
               (i.safety_stock - i.quantity) AS shortage
        FROM inventory i JOIN warehouses w ON i.warehouse_id = w.id
        WHERE i.quantity < i.safety_stock
    """
    params = ()
    if warehouse_id:
        sql += " AND i.warehouse_id=?"
        params = (warehouse_id,)
    sql += " ORDER BY shortage DESC"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]
