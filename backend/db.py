import os
import psycopg2
import psycopg2.pool
import psycopg2.extras
from datetime import datetime

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://localhost/warehouse")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
if "sslmode" not in DATABASE_URL:
    sep = "&" if "?" in DATABASE_URL else "?"
    DATABASE_URL += f"{sep}sslmode=require"

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        _pool = psycopg2.pool.ThreadedConnectionPool(2, 20, DATABASE_URL)
    return _pool


class DBConn:
    """Thin psycopg2 wrapper that mirrors the sqlite3 connection API."""

    def __init__(self, pg_conn: psycopg2.extensions.connection):
        self._conn = pg_conn
        self._cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def execute(self, sql: str, params=None):
        self._cur.execute(sql, params)
        return self._cur

    def executemany(self, sql: str, seq):
        self._cur.executemany(sql, seq)
        return self._cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        try:
            self._conn.rollback()
        except Exception:
            pass
        _get_pool().putconn(self._conn)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


def get_conn() -> DBConn:
    conn = _get_pool().getconn()
    return DBConn(conn)


# ── Schema ────────────────────────────────────────────────────────────────────

_DDL = [
    """
    CREATE TABLE IF NOT EXISTS warehouses (
        id       TEXT PRIMARY KEY,
        name     TEXT NOT NULL,
        location TEXT NOT NULL,
        capacity INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        sku          TEXT PRIMARY KEY,
        name         TEXT NOT NULL,
        category     TEXT NOT NULL,
        unit         TEXT NOT NULL,
        safety_stock INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS storage_locations (
        location_id  TEXT PRIMARY KEY,
        warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
        zone_type    TEXT NOT NULL,
        cb_category  TEXT,
        label        TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory (
        id          SERIAL PRIMARY KEY,
        location_id TEXT NOT NULL REFERENCES storage_locations(location_id),
        sku         TEXT NOT NULL REFERENCES products(sku),
        quantity    INTEGER NOT NULL DEFAULT 0,
        acct_status TEXT NOT NULL DEFAULT 'AVAILABLE',
        updated_at  TEXT NOT NULL,
        UNIQUE(location_id, sku)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inbound_orders (
        order_id     TEXT PRIMARY KEY,
        warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
        supplier     TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'DRAFT',
        created_at   TEXT NOT NULL,
        created_by   TEXT NOT NULL DEFAULT 'system'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inbound_order_details (
        id           SERIAL PRIMARY KEY,
        order_id     TEXT NOT NULL REFERENCES inbound_orders(order_id),
        sku          TEXT NOT NULL REFERENCES products(sku),
        qty_expected INTEGER NOT NULL,
        qty_actual   INTEGER,
        shortage_qty INTEGER NOT NULL DEFAULT 0,
        excess_qty   INTEGER NOT NULL DEFAULT 0,
        damage_qty   INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS transfer_orders (
        order_id   TEXT PRIMARY KEY,
        from_wh    TEXT NOT NULL REFERENCES warehouses(id),
        to_wh      TEXT NOT NULL REFERENCES warehouses(id),
        status     TEXT NOT NULL DEFAULT 'DRAFT',
        ref_doc    TEXT,
        created_at TEXT NOT NULL,
        created_by TEXT NOT NULL DEFAULT 'system'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS transfer_order_details (
        id           SERIAL PRIMARY KEY,
        order_id     TEXT NOT NULL REFERENCES transfer_orders(order_id),
        sku          TEXT NOT NULL REFERENCES products(sku),
        qty_ordered  INTEGER NOT NULL,
        qty_issued   INTEGER,
        qty_received INTEGER,
        shortage_qty INTEGER NOT NULL DEFAULT 0,
        excess_qty   INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS outbound_orders (
        order_id     TEXT PRIMARY KEY,
        warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
        customer     TEXT NOT NULL,
        status       TEXT NOT NULL DEFAULT 'DRAFT',
        created_at   TEXT NOT NULL,
        created_by   TEXT NOT NULL DEFAULT 'system'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS outbound_order_details (
        id           SERIAL PRIMARY KEY,
        order_id     TEXT NOT NULL REFERENCES outbound_orders(order_id),
        sku          TEXT NOT NULL REFERENCES products(sku),
        qty_ordered  INTEGER NOT NULL,
        qty_picked   INTEGER,
        shortage_qty INTEGER NOT NULL DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cycle_counts (
        count_id     TEXT PRIMARY KEY,
        warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
        count_type   TEXT NOT NULL DEFAULT 'MANUAL',
        location_id  TEXT REFERENCES storage_locations(location_id),
        status       TEXT NOT NULL DEFAULT 'DRAFT',
        created_at   TEXT NOT NULL,
        created_by   TEXT NOT NULL DEFAULT 'system'
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cycle_count_details (
        id          SERIAL PRIMARY KEY,
        count_id    TEXT NOT NULL REFERENCES cycle_counts(count_id),
        location_id TEXT NOT NULL REFERENCES storage_locations(location_id),
        sku         TEXT NOT NULL REFERENCES products(sku),
        qty_system  INTEGER NOT NULL,
        qty_actual  INTEGER,
        difference  INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS inventory_movements (
        movement_id   TEXT PRIMARY KEY,
        movement_type TEXT NOT NULL,
        from_location TEXT REFERENCES storage_locations(location_id),
        to_location   TEXT REFERENCES storage_locations(location_id),
        sku           TEXT NOT NULL REFERENCES products(sku),
        quantity      INTEGER NOT NULL,
        t_code        TEXT NOT NULL,
        created_by    TEXT NOT NULL DEFAULT 'system',
        created_at    TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS approvals (
        approval_id TEXT PRIMARY KEY,
        ref_type    TEXT NOT NULL,
        ref_id      TEXT NOT NULL,
        status      TEXT NOT NULL DEFAULT 'PENDING',
        approved_by TEXT,
        approved_at TEXT,
        note        TEXT,
        created_at  TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claims (
        claim_id            TEXT PRIMARY KEY,
        t_code              TEXT NOT NULL,
        trigger_movement_id TEXT REFERENCES inventory_movements(movement_id),
        claim_type          TEXT NOT NULL,
        physical_wh         TEXT NOT NULL REFERENCES warehouses(id),
        account_wh          TEXT NOT NULL REFERENCES warehouses(id),
        initiated_by        TEXT NOT NULL REFERENCES warehouses(id),
        responsible_party   TEXT NOT NULL,
        shortage_qty        INTEGER NOT NULL DEFAULT 0,
        excess_qty          INTEGER NOT NULL DEFAULT 0,
        status              TEXT NOT NULL DEFAULT 'PENDING',
        resolved_at         TEXT,
        created_at          TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS claim_logs (
        id        SERIAL PRIMARY KEY,
        claim_id  TEXT NOT NULL REFERENCES claims(claim_id),
        action    TEXT NOT NULL,
        actor     TEXT NOT NULL,
        note      TEXT,
        timestamp TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_inventory_sku        ON inventory(sku)",
    "CREATE INDEX IF NOT EXISTS idx_inventory_location   ON inventory(location_id)",
    "CREATE INDEX IF NOT EXISTS idx_movements_sku        ON inventory_movements(sku)",
    "CREATE INDEX IF NOT EXISTS idx_movements_t_code     ON inventory_movements(t_code)",
    "CREATE INDEX IF NOT EXISTS idx_movements_created    ON inventory_movements(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_claims_status        ON claims(status)",
    "CREATE INDEX IF NOT EXISTS idx_claims_physical_wh   ON claims(physical_wh)",
    "CREATE INDEX IF NOT EXISTS idx_claims_account_wh    ON claims(account_wh)",
    "CREATE INDEX IF NOT EXISTS idx_storage_warehouse    ON storage_locations(warehouse_id)",
]


def init_db():
    with get_conn() as conn:
        for stmt in _DDL:
            conn.execute(stmt)
        conn.commit()


# ── Seed Data ─────────────────────────────────────────────────────────────────

def seed_data():
    with get_conn() as conn:
        for t in [
            "claim_logs", "claims", "approvals", "inventory_movements",
            "cycle_count_details", "cycle_counts",
            "outbound_order_details", "outbound_orders",
            "transfer_order_details", "transfer_orders",
            "inbound_order_details", "inbound_orders",
            "inventory", "storage_locations", "products", "warehouses",
        ]:
            conn.execute(f"DELETE FROM {t}")

        conn.executemany("INSERT INTO warehouses VALUES (%s,%s,%s,%s)", [
            ("W1", "北區倉", "台北", 10000),
            ("W2", "中區倉", "台中",  8000),
            ("W3", "南區倉", "高雄", 12000),
        ])

        conn.executemany("INSERT INTO products VALUES (%s,%s,%s,%s,%s)", [
            ("P001", "包裝紙箱(大)", "包材", "個",  200),
            ("P002", "包裝紙箱(小)", "包材", "個",  150),
            ("P003", "氣泡紙",       "包材", "捲",   80),
            ("P004", "棧板",         "物流", "片",  100),
            ("P005", "封箱膠帶",     "包材", "捲",  300),
            ("P006", "防撞角條",     "包材", "條",  100),
            ("P007", "標籤貼紙",     "包材", "張",  500),
            ("P008", "棉繩",         "包材", "捆",   50),
            ("P009", "防潮袋",       "包材", "個",  200),
            ("P010", "保麗龍內襯",   "包材", "片",  120),
        ])

        skus = ["P001","P002","P003","P004","P005","P006","P007","P008","P009","P010"]
        locs = []
        for wh in ["W1", "W2", "W3"]:
            for i, sku in enumerate(skus, 1):
                locs.append((f"{wh}-PICK-{i:03d}", wh, "PICKING",        None,      f"{wh} 揀貨區 {sku}"))
            for i in range(1, 4):
                locs.append((f"{wh}-BUF-{i:03d}",  wh, "BUFFER",         None,      f"{wh} 後備區 B{i:03d}"))
            locs.append((f"{wh}-PROB-001",           wh, "PROBLEM",        None,      f"{wh} 問題品區"))
            for cat, label in [
                ("SHORT",  "轉倉短少區"),
                ("QUALITY","品質異常區"),
                ("SPEC",   "規格不符區"),
                ("COUNT",  "盤點差異區"),
                ("DAMAGE", "損毀品區"),
            ]:
                locs.append((f"{wh}-CB-{cat}-001", wh, "COLLECT_BUFFER", cat, f"{wh} 集貨緩衝 {label}"))
            locs.append((f"{wh}-DISU-001",          wh, "DISUSE",         None,      f"{wh} 廢棄品區"))

        conn.executemany("INSERT INTO storage_locations VALUES (%s,%s,%s,%s,%s)", locs)

        now = "2026-05-23T00:00:00"
        raw = {
            "W1": [120,300, 50,200,600, 40,1200, 90,320, 75],
            "W2": [850,420,180, 80,150,220, 480, 15, 60,280],
            "W3": [ 60, 90, 25,350,820, 35,2100,130,410, 30],
        }
        inv = []
        for wh, qtys in raw.items():
            for idx, (sku, total) in enumerate(zip(skus, qtys), 1):
                pick = max(1, round(total * 0.3))
                buf  = total - pick
                inv.append((f"{wh}-PICK-{idx:03d}", sku, pick, "AVAILABLE", now))
                buf_loc = f"{wh}-BUF-{((idx-1)%3)+1:03d}"
                inv.append((buf_loc, sku, buf, "AVAILABLE", now))

        inv.append(("W1-CB-DAMAGE-001","P010", 3, "FROZEN",         now))
        inv.append(("W2-CB-COUNT-001","P003", 5, "FROZEN",          now))
        inv.append(("W3-DISU-001",    "P006", 4, "PENDING_WRITEOFF",now))

        seen = {}
        for loc, sku, qty, status, ts in inv:
            key = (loc, sku)
            if key in seen:
                seen[key] = (loc, sku, seen[key][2] + qty, status, ts)
            else:
                seen[key] = (loc, sku, qty, status, ts)
        conn.executemany(
            "INSERT INTO inventory(location_id,sku,quantity,acct_status,updated_at) VALUES (%s,%s,%s,%s,%s)",
            seen.values()
        )

        conn.executemany("INSERT INTO inbound_orders VALUES (%s,%s,%s,%s,%s,%s)", [
            ("INB-20260510-001","W1","包材供應商A","COMPLETED","2026-05-10T09:00:00","W1-OP"),
            ("INB-20260515-001","W2","包材供應商B","COMPLETED","2026-05-15T10:00:00","W2-OP"),
            ("INB-20260523-001","W3","包材供應商A","RECEIVING","2026-05-23T08:00:00","W3-OP"),
        ])
        conn.executemany(
            "INSERT INTO inbound_order_details(order_id,sku,qty_expected,qty_actual,shortage_qty,excess_qty,damage_qty) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            [
                ("INB-20260510-001","P002",500,500,0,0,0),
                ("INB-20260510-001","P005",300,300,0,0,0),
                ("INB-20260515-001","P003",100,92,8,0,0),
                ("INB-20260515-001","P009",200,200,0,0,0),
                ("INB-20260523-001","P001",200,None,0,0,0),
                ("INB-20260523-001","P004",150,None,0,0,0),
            ]
        )

        conn.executemany("INSERT INTO transfer_orders VALUES (%s,%s,%s,%s,%s,%s,%s)", [
            ("TRF-20260501-001","W2","W1","COMPLETED", None,          "2026-05-01T08:00:00","W2-OP"),
            ("TRF-20260515-001","W2","W3","IN_TRANSIT", None,         "2026-05-15T09:00:00","W2-OP"),
            ("TRF-20260518-001","W2","W1","RECEIVED",  "車號 TRK-018","2026-05-18T10:00:00","W2-OP"),
            ("TRF-20260520-001","W3","W2","COMPLETED",  None,         "2026-05-20T11:00:00","W3-OP"),
            ("TRF-20260521-001","W1","W3","IN_TRANSIT", None,         "2026-05-21T09:00:00","W1-OP"),
        ])
        conn.executemany(
            "INSERT INTO transfer_order_details(order_id,sku,qty_ordered,qty_issued,qty_received,shortage_qty,excess_qty) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            [
                ("TRF-20260501-001","P001",200,200,200,0,0),
                ("TRF-20260515-001","P001",100,100,None,0,0),
                ("TRF-20260518-001","P006",100,100,90,10,0),
                ("TRF-20260520-001","P004",150,150,150,0,0),
                ("TRF-20260521-001","P007",600,600,None,0,0),
            ]
        )

        conn.executemany("INSERT INTO outbound_orders VALUES (%s,%s,%s,%s,%s,%s)", [
            ("OUT-20260519-001","W1","電商平台A","COMPLETED","2026-05-19T13:00:00","W1-OP"),
            ("OUT-20260521-001","W2","電商平台B","COMPLETED","2026-05-21T14:00:00","W2-OP"),
            ("OUT-20260522-001","W3","電商平台C","PICKING",  "2026-05-22T10:00:00","W3-OP"),
        ])
        conn.executemany(
            "INSERT INTO outbound_order_details(order_id,sku,qty_ordered,qty_picked,shortage_qty) VALUES (%s,%s,%s,%s,%s)",
            [
                ("OUT-20260519-001","P001",50,50,0),
                ("OUT-20260521-001","P007",200,200,0),
                ("OUT-20260522-001","P005",100,95,5),
            ]
        )

        conn.executemany("INSERT INTO cycle_counts VALUES (%s,%s,%s,%s,%s,%s,%s)", [
            ("CNT-20260520-001","W1","MANUAL","W1-PICK-003","COMPLETED","2026-05-20T09:00:00","W1-OP"),
            ("CNT-20260522-001","W2","SCHEDULED",None,"IN_PROGRESS","2026-05-22T09:00:00","system"),
        ])
        conn.executemany(
            "INSERT INTO cycle_count_details(count_id,location_id,sku,qty_system,qty_actual,difference) VALUES (%s,%s,%s,%s,%s,%s)",
            [
                ("CNT-20260520-001","W1-PICK-003","P003",15,10,-5),
                ("CNT-20260522-001","W2-PICK-004","P004",25,None,None),
                ("CNT-20260522-001","W2-PICK-008","P008", 5,None,None),
            ]
        )

        conn.executemany(
            "INSERT INTO inventory_movements(movement_id,movement_type,from_location,to_location,sku,quantity,t_code,created_by,created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                ("MVT-20260501-001","TRANSFER_OUT","W2-PICK-001",None,         "P001",200,"TRF-20260501-001","W2-OP","2026-05-01T10:00:00"),
                ("MVT-20260501-002","TRANSFER_IN", None,"W1-BUF-001",          "P001",200,"TRF-20260501-001","W1-OP","2026-05-01T16:00:00"),
                ("MVT-20260518-001","TRANSFER_OUT","W2-PICK-006",None,         "P006",100,"TRF-20260518-001","W2-OP","2026-05-18T11:00:00"),
                ("MVT-20260518-002","TRANSFER_IN", None,"W1-PICK-006",         "P006", 90,"TRF-20260518-001","W1-OP","2026-05-18T17:00:00"),
                ("MVT-20260520-001","COUNT_ADJ",   "W1-PICK-003",None,         "P003",  5,"CNT-20260520-001","W1-OP","2026-05-20T10:30:00"),
                ("MVT-20260520-002","ZONE_MOVE",    None,"W2-CB-COUNT-001",    "P003",  5,"CNT-20260520-001","W1-OP","2026-05-20T10:35:00"),
                ("MVT-20260522-001","ZONE_MOVE",   "W1-PICK-010","W1-PROB-001","P010",  3,"CLM-20260522-002","W1-OP","2026-05-22T09:00:00"),
                ("MVT-20260522-002","ZONE_MOVE",   "W1-PROB-001","W1-CB-DAMAGE-001","P010",3,"CLM-20260522-002","W1-OP","2026-05-22T14:00:00"),
                ("MVT-20260522-003","ZONE_MOVE",   "W3-PICK-006","W3-DISU-001","P006",  4,"CLM-20260519-003","W3-OP","2026-05-22T11:00:00"),
            ]
        )

        conn.executemany(
            "INSERT INTO claims VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            [
                (
                    "CLM-20260518-001","TRF-20260518-001","MVT-20260518-002",
                    "TRANSFER_SHORTAGE","W1","W2","W1","ORIGIN_WH",
                    10,0,"PENDING",None,"2026-05-18T17:30:00"
                ),
                (
                    "CLM-20260520-001","CNT-20260520-001","MVT-20260520-001",
                    "COUNT_DISCREPANCY","W1","W1","W1","SELF",
                    5,0,"IN_COLLECT_BUFFER",None,"2026-05-20T10:40:00"
                ),
                (
                    "CLM-20260515-002","INB-20260515-001",None,
                    "INBOUND_SHORTAGE","W2","W2","W2","SUPPLIER",
                    8,0,"INVESTIGATING",None,"2026-05-15T11:00:00"
                ),
                (
                    "CLM-20260522-002","MVT-20260522-001","MVT-20260522-001",
                    "DAMAGE","W1","W1","W1","SELF",
                    3,0,"IN_COLLECT_BUFFER",None,"2026-05-22T09:10:00"
                ),
                (
                    "CLM-20260522-003","OUT-20260522-001",None,
                    "PICKING_SHORTAGE","W3","W3","W3","SELF",
                    5,0,"PENDING",None,"2026-05-22T10:30:00"
                ),
                (
                    "CLM-20260519-003","MVT-20260522-003","MVT-20260522-003",
                    "DAMAGE","W3","W3","W3","SELF",
                    4,0,"DISUSE_PENDING",None,"2026-05-19T08:00:00"
                ),
            ]
        )

        conn.executemany(
            "INSERT INTO claim_logs(claim_id,action,actor,note,timestamp) VALUES (%s,%s,%s,%s,%s)",
            [
                ("CLM-20260518-001","建立",         "W1-OP","TRF-20260518-001 收貨差異 10 個，自動建立","2026-05-18T17:30:00"),
                ("CLM-20260518-001","通知對方",      "system","已通知 W2 確認出庫數量",               "2026-05-18T17:31:00"),
                ("CLM-20260520-001","建立",         "W1-OP","盤點 W1-PICK-003 發現 P003 差異 -5",    "2026-05-20T10:40:00"),
                ("CLM-20260520-001","移至集貨緩衝", "W1-OP","移入 CB-COUNT 待處理",                   "2026-05-20T11:00:00"),
                ("CLM-20260515-002","建立",         "W2-OP","INB-20260515-001 P003 短少 8 個",       "2026-05-15T11:00:00"),
                ("CLM-20260515-002","開始調查",     "W2-OP","聯繫供應商確認出貨單",                   "2026-05-15T14:00:00"),
                ("CLM-20260522-002","建立",         "W1-OP","P010 揀貨時發現損毀 3 個",               "2026-05-22T09:10:00"),
                ("CLM-20260522-002","移入問題區",   "W1-OP","移至 W1-PROB-001",                      "2026-05-22T09:15:00"),
                ("CLM-20260522-002","移至集貨緩衝", "W1-OP","判定損毀，移入 CB-DAMAGE",               "2026-05-22T14:05:00"),
                ("CLM-20260522-003","建立",         "W3-OP","OUT-20260522-001 P005 揀貨短少 5 個",   "2026-05-22T10:30:00"),
                ("CLM-20260519-003","申請除帳",     "W3-OP","P006 損毀 4 個，申請除帳核准",           "2026-05-22T11:10:00"),
            ]
        )

        conn.execute(
            "INSERT INTO approvals VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            ("APV-20260522-001","WRITEOFF","CLM-20260519-003","PENDING",
             None, None,"W3 P006 損毀 4 個，待主管核准除帳","2026-05-22T11:10:00")
        )

        conn.commit()


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_warehouse_inventory_summary():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT sl.warehouse_id, i.sku, p.name, p.unit, p.safety_stock,
                   SUM(i.quantity) AS total_qty
              FROM inventory i
              JOIN storage_locations sl ON i.location_id = sl.location_id
              JOIN products p ON i.sku = p.sku
             WHERE sl.zone_type IN ('PICKING','BUFFER')
               AND i.acct_status = 'AVAILABLE'
             GROUP BY sl.warehouse_id, i.sku, p.name, p.unit, p.safety_stock
             ORDER BY sl.warehouse_id, i.sku
        """).fetchall()
    return [dict(r) for r in rows]


def get_problem_stock_summary():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT sl.warehouse_id, sl.zone_type, sl.cb_category,
                   i.sku, p.name, p.unit,
                   SUM(i.quantity) AS quantity, i.acct_status
              FROM inventory i
              JOIN storage_locations sl ON i.location_id = sl.location_id
              JOIN products p ON i.sku = p.sku
             WHERE sl.zone_type IN ('PROBLEM','COLLECT_BUFFER','DISUSE')
               AND i.quantity > 0
             GROUP BY sl.warehouse_id, sl.zone_type, sl.cb_category,
                      i.sku, p.name, p.unit, i.acct_status
             ORDER BY sl.warehouse_id, sl.zone_type
        """).fetchall()
    return [dict(r) for r in rows]


# ── Startup ───────────────────────────────────────────────────────────────────

def ensure_ready():
    init_db()
    with get_conn() as conn:
        has_data = conn.execute("SELECT 1 FROM warehouses LIMIT 1").fetchone()
    if not has_data:
        seed_data()
