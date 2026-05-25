import db


def _available_qty(warehouse_id: str, sku: str, conn) -> int:
    row = conn.execute("""
        SELECT SUM(i.quantity) AS qty
          FROM inventory i
          JOIN storage_locations sl ON i.location_id = sl.location_id
         WHERE sl.warehouse_id=%s AND i.sku=%s
           AND sl.zone_type IN ('PICKING','BUFFER')
           AND i.acct_status='AVAILABLE'
    """, (warehouse_id, sku)).fetchone()
    return row["qty"] or 0


def get_inventory(sku: str, warehouse_id: str = None) -> dict:
    conn = db.get_conn()
    if not conn.execute("SELECT 1 FROM products WHERE sku=%s", (sku,)).fetchone():
        conn.close()
        return {"error": f"找不到 SKU {sku}"}

    product = conn.execute("SELECT * FROM products WHERE sku=%s", (sku,)).fetchone()

    if warehouse_id:
        wh = conn.execute("SELECT * FROM warehouses WHERE id=%s", (warehouse_id,)).fetchone()
        if not wh:
            conn.close()
            return {"error": f"找不到倉庫 {warehouse_id}"}
        qty = _available_qty(warehouse_id, sku, conn)
        conn.close()
        shortage = max(0, product["safety_stock"] - qty)
        return {
            "warehouse_id": warehouse_id,
            "warehouse_name": wh["name"],
            "sku": sku,
            "product_name": product["name"],
            "unit": product["unit"],
            "quantity": qty,
            "safety_stock": product["safety_stock"],
            "status": "低庫存" if qty < product["safety_stock"] else "正常",
            "shortage": shortage,
        }

    warehouses = conn.execute("SELECT id, name FROM warehouses ORDER BY id").fetchall()
    result = []
    total = 0
    for wh in warehouses:
        qty = _available_qty(wh["id"], sku, conn)
        shortage = max(0, product["safety_stock"] - qty)
        result.append({
            "warehouse_id": wh["id"],
            "warehouse_name": wh["name"],
            "sku": sku,
            "product_name": product["name"],
            "unit": product["unit"],
            "quantity": qty,
            "safety_stock": product["safety_stock"],
            "status": "低庫存" if qty < product["safety_stock"] else "正常",
            "shortage": shortage,
        })
        total += qty
    conn.close()
    return {
        "sku": sku,
        "product_name": product["name"],
        "unit": product["unit"],
        "total_quantity": total,
        "safety_stock": product["safety_stock"],
        "warehouses": result,
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
    conn = db.get_conn()
    sql = """
        SELECT sl.warehouse_id, w.name AS warehouse_name,
               i.sku, p.name AS product_name, p.unit,
               SUM(i.quantity) AS quantity, p.safety_stock,
               p.safety_stock - SUM(i.quantity) AS shortage
          FROM inventory i
          JOIN storage_locations sl ON i.location_id = sl.location_id
          JOIN warehouses w ON sl.warehouse_id = w.id
          JOIN products p ON i.sku = p.sku
         WHERE sl.zone_type IN ('PICKING','BUFFER')
           AND i.acct_status = 'AVAILABLE'
    """
    params = []
    if warehouse_id:
        sql += " AND sl.warehouse_id=%s"
        params.append(warehouse_id)
    sql += """
         GROUP BY sl.warehouse_id, w.name, i.sku, p.name, p.unit, p.safety_stock
        HAVING SUM(i.quantity) < p.safety_stock
         ORDER BY shortage DESC
    """
    rows = conn.execute(sql, params or None).fetchall()
    conn.close()
    return [dict(r) for r in rows]
