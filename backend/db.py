import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "warehouse.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# ── Schema ────────────────────────────────────────────────────────────────────

def init_db():
    conn = get_conn()
    conn.executescript("""
        -- ── 主資料 ──────────────────────────────────────────────────────────
        CREATE TABLE IF NOT EXISTS warehouses (
            id       TEXT PRIMARY KEY,
            name     TEXT NOT NULL,
            location TEXT NOT NULL,
            capacity INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS products (
            sku          TEXT PRIMARY KEY,
            name         TEXT NOT NULL,
            category     TEXT NOT NULL,
            unit         TEXT NOT NULL,
            safety_stock INTEGER NOT NULL DEFAULT 0
        );

        -- ── 儲位主檔 ─────────────────────────────────────────────────────────
        -- zone_type: PICKING | BUFFER | PROBLEM | COLLECT_BUFFER | DISUSE
        -- cb_category (COLLECT_BUFFER 才填): SHORT | QUALITY | SPEC | COUNT | DAMAGE
        CREATE TABLE IF NOT EXISTS storage_locations (
            location_id  TEXT PRIMARY KEY,
            warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
            zone_type    TEXT NOT NULL,
            cb_category  TEXT,
            label        TEXT NOT NULL
        );

        -- ── 庫存（到儲位層）─────────────────────────────────────────────────
        -- acct_status: AVAILABLE | FROZEN | PENDING_WRITEOFF | WRITTEN_OFF
        CREATE TABLE IF NOT EXISTS inventory (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id TEXT NOT NULL REFERENCES storage_locations(location_id),
            sku         TEXT NOT NULL REFERENCES products(sku),
            quantity    INTEGER NOT NULL DEFAULT 0,
            acct_status TEXT NOT NULL DEFAULT 'AVAILABLE',
            updated_at  TEXT NOT NULL,
            UNIQUE(location_id, sku)
        );

        -- ── 入庫單（ASN）────────────────────────────────────────────────────
        -- status: DRAFT | RECEIVING | COMPLETED | CANCELLED
        CREATE TABLE IF NOT EXISTS inbound_orders (
            order_id     TEXT PRIMARY KEY,
            warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
            supplier     TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'DRAFT',
            created_at   TEXT NOT NULL,
            created_by   TEXT NOT NULL DEFAULT 'system'
        );

        CREATE TABLE IF NOT EXISTS inbound_order_details (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id     TEXT NOT NULL REFERENCES inbound_orders(order_id),
            sku          TEXT NOT NULL REFERENCES products(sku),
            qty_expected INTEGER NOT NULL,
            qty_actual   INTEGER,
            shortage_qty INTEGER NOT NULL DEFAULT 0,
            excess_qty   INTEGER NOT NULL DEFAULT 0,
            damage_qty   INTEGER NOT NULL DEFAULT 0
        );

        -- ── 調撥單（Stock Transfer）──────────────────────────────────────────
        -- status: DRAFT | ISSUED | IN_TRANSIT | RECEIVED | COMPLETED | CANCELLED
        CREATE TABLE IF NOT EXISTS transfer_orders (
            order_id   TEXT PRIMARY KEY,
            from_wh    TEXT NOT NULL REFERENCES warehouses(id),
            to_wh      TEXT NOT NULL REFERENCES warehouses(id),
            status     TEXT NOT NULL DEFAULT 'DRAFT',
            ref_doc    TEXT,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL DEFAULT 'system'
        );

        CREATE TABLE IF NOT EXISTS transfer_order_details (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id     TEXT NOT NULL REFERENCES transfer_orders(order_id),
            sku          TEXT NOT NULL REFERENCES products(sku),
            qty_ordered  INTEGER NOT NULL,
            qty_issued   INTEGER,
            qty_received INTEGER,
            shortage_qty INTEGER NOT NULL DEFAULT 0,
            excess_qty   INTEGER NOT NULL DEFAULT 0
        );

        -- ── 出貨單 ──────────────────────────────────────────────────────────
        -- status: DRAFT | PICKING | COMPLETED | CANCELLED
        CREATE TABLE IF NOT EXISTS outbound_orders (
            order_id     TEXT PRIMARY KEY,
            warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
            customer     TEXT NOT NULL,
            status       TEXT NOT NULL DEFAULT 'DRAFT',
            created_at   TEXT NOT NULL,
            created_by   TEXT NOT NULL DEFAULT 'system'
        );

        CREATE TABLE IF NOT EXISTS outbound_order_details (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id     TEXT NOT NULL REFERENCES outbound_orders(order_id),
            sku          TEXT NOT NULL REFERENCES products(sku),
            qty_ordered  INTEGER NOT NULL,
            qty_picked   INTEGER,
            shortage_qty INTEGER NOT NULL DEFAULT 0
        );

        -- ── 盤點單 ──────────────────────────────────────────────────────────
        -- count_type: SCHEDULED | MANUAL
        -- status: DRAFT | IN_PROGRESS | COMPLETED
        CREATE TABLE IF NOT EXISTS cycle_counts (
            count_id     TEXT PRIMARY KEY,
            warehouse_id TEXT NOT NULL REFERENCES warehouses(id),
            count_type   TEXT NOT NULL DEFAULT 'MANUAL',
            location_id  TEXT REFERENCES storage_locations(location_id),
            status       TEXT NOT NULL DEFAULT 'DRAFT',
            created_at   TEXT NOT NULL,
            created_by   TEXT NOT NULL DEFAULT 'system'
        );

        CREATE TABLE IF NOT EXISTS cycle_count_details (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            count_id    TEXT NOT NULL REFERENCES cycle_counts(count_id),
            location_id TEXT NOT NULL REFERENCES storage_locations(location_id),
            sku         TEXT NOT NULL REFERENCES products(sku),
            qty_system  INTEGER NOT NULL,
            qty_actual  INTEGER,
            difference  INTEGER
        );

        -- ── 庫存異動紀錄（所有作業的原始紀錄）──────────────────────────────
        -- movement_type: INBOUND | TRANSFER_OUT | TRANSFER_IN | OUTBOUND
        --                ZONE_MOVE | WRITEOFF | RECOVER | COUNT_ADJ
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
        );

        -- ── 審批（除帳 / Claim 結案）─────────────────────────────────────────
        -- ref_type: WRITEOFF | CLAIM_CLOSE
        -- status: PENDING | APPROVED | REJECTED
        CREATE TABLE IF NOT EXISTS approvals (
            approval_id TEXT PRIMARY KEY,
            ref_type    TEXT NOT NULL,
            ref_id      TEXT NOT NULL,
            status      TEXT NOT NULL DEFAULT 'PENDING',
            approved_by TEXT,
            approved_at TEXT,
            note        TEXT,
            created_at  TEXT NOT NULL
        );

        -- ── 異議單 ──────────────────────────────────────────────────────────
        -- claim_type: TRANSFER_SHORTAGE | TRANSFER_EXCESS
        --             INBOUND_SHORTAGE | PICKING_SHORTAGE | COUNT_DISCREPANCY | DAMAGE
        -- physical_wh : 物品實際所在倉
        -- account_wh  : 帳務責任倉（跨倉才會不同）
        -- responsible_party: ORIGIN_WH | DEST_WH | SELF | LOGISTICS | SUPPLIER
        -- status: PENDING | INVESTIGATING | IN_COLLECT_BUFFER | DISUSE_PENDING
        --         RESOLVED | WRITTEN_OFF | REJECTED
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
        );

        CREATE TABLE IF NOT EXISTS claim_logs (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            claim_id  TEXT NOT NULL REFERENCES claims(claim_id),
            action    TEXT NOT NULL,
            actor     TEXT NOT NULL,
            note      TEXT,
            timestamp TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


# ── Seed Data ─────────────────────────────────────────────────────────────────

def seed_data():
    conn = get_conn()
    c = conn.cursor()

    # ── 清空（保留 schema）──────────────────────────────────────────────────
    for t in [
        "claim_logs", "claims", "approvals", "inventory_movements",
        "cycle_count_details", "cycle_counts",
        "outbound_order_details", "outbound_orders",
        "transfer_order_details", "transfer_orders",
        "inbound_order_details", "inbound_orders",
        "inventory", "storage_locations", "products", "warehouses",
    ]:
        c.execute(f"DELETE FROM {t}")

    # ── 倉庫 ────────────────────────────────────────────────────────────────
    c.executemany("INSERT INTO warehouses VALUES (?,?,?,?)", [
        ("W1", "北區倉", "台北", 10000),
        ("W2", "中區倉", "台中",  8000),
        ("W3", "南區倉", "高雄", 12000),
    ])

    # ── 品項 ────────────────────────────────────────────────────────────────
    c.executemany("INSERT INTO products VALUES (?,?,?,?,?)", [
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

    # ── 儲位主檔 ─────────────────────────────────────────────────────────────
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

    c.executemany("INSERT INTO storage_locations VALUES (?,?,?,?,?)", locs)

    # ── 庫存分佈（PICK 30% / BUF 70%，低庫存品項保持原比例）──────────────
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

    # 損毀品示範：P010 已移入集貨緩衝 CB-DAMAGE（claim 狀態 IN_COLLECT_BUFFER）
    inv.append(("W1-CB-DAMAGE-001","P010", 3, "FROZEN",         now))
    # 集貨緩衝示範：W2-CB-COUNT-001 有 P003 盤點差異 5 個（FROZEN）
    inv.append(("W2-CB-COUNT-001","P003", 5, "FROZEN",          now))
    # 廢棄品示範：W3-DISU-001 有 P006 待除帳 4 個（PENDING_WRITEOFF）
    inv.append(("W3-DISU-001",    "P006", 4, "PENDING_WRITEOFF",now))

    # 避免 BUF unique 衝突（多個 SKU 到同一個 BUF loc）
    seen = {}
    for loc, sku, qty, status, ts in inv:
        key = (loc, sku)
        if key in seen:
            seen[key] = (loc, sku, seen[key][2] + qty, status, ts)
        else:
            seen[key] = (loc, sku, qty, status, ts)
    c.executemany(
        "INSERT INTO inventory(location_id,sku,quantity,acct_status,updated_at) VALUES (?,?,?,?,?)",
        seen.values()
    )

    # ── 入庫單 ──────────────────────────────────────────────────────────────
    c.executemany("INSERT INTO inbound_orders VALUES (?,?,?,?,?,?)", [
        ("INB-20260510-001","W1","包材供應商A","COMPLETED","2026-05-10T09:00:00","W1-OP"),
        ("INB-20260515-001","W2","包材供應商B","COMPLETED","2026-05-15T10:00:00","W2-OP"),
        ("INB-20260523-001","W3","包材供應商A","RECEIVING","2026-05-23T08:00:00","W3-OP"),
    ])
    c.executemany(
        "INSERT INTO inbound_order_details(order_id,sku,qty_expected,qty_actual,shortage_qty,excess_qty,damage_qty) VALUES (?,?,?,?,?,?,?)",
        [
            ("INB-20260510-001","P002",500,500,0,0,0),
            ("INB-20260510-001","P005",300,300,0,0,0),
            # INB-20260515-001：P003 收到 92，短少 8
            ("INB-20260515-001","P003",100,92,8,0,0),
            ("INB-20260515-001","P009",200,200,0,0,0),
            # INB-20260523-001：尚未驗收
            ("INB-20260523-001","P001",200,None,0,0,0),
            ("INB-20260523-001","P004",150,None,0,0,0),
        ]
    )

    # ── 調撥單 ──────────────────────────────────────────────────────────────
    c.executemany("INSERT INTO transfer_orders VALUES (?,?,?,?,?,?,?)", [
        ("TRF-20260501-001","W2","W1","COMPLETED", None,          "2026-05-01T08:00:00","W2-OP"),
        ("TRF-20260515-001","W2","W3","IN_TRANSIT", None,         "2026-05-15T09:00:00","W2-OP"),
        ("TRF-20260518-001","W2","W1","RECEIVED",  "車號 TRK-018","2026-05-18T10:00:00","W2-OP"),
        ("TRF-20260520-001","W3","W2","COMPLETED",  None,         "2026-05-20T11:00:00","W3-OP"),
        ("TRF-20260521-001","W1","W3","IN_TRANSIT", None,         "2026-05-21T09:00:00","W1-OP"),
    ])
    c.executemany(
        "INSERT INTO transfer_order_details(order_id,sku,qty_ordered,qty_issued,qty_received,shortage_qty,excess_qty) VALUES (?,?,?,?,?,?,?)",
        [
            ("TRF-20260501-001","P001",200,200,200,0,0),
            ("TRF-20260515-001","P001",100,100,None,0,0),
            # TRF-20260518-001：P006 發出 100，到貨 90，短少 10 → 產生跨倉 Claim
            ("TRF-20260518-001","P006",100,100,90,10,0),
            ("TRF-20260520-001","P004",150,150,150,0,0),
            ("TRF-20260521-001","P007",600,600,None,0,0),
        ]
    )

    # ── 出貨單 ──────────────────────────────────────────────────────────────
    c.executemany("INSERT INTO outbound_orders VALUES (?,?,?,?,?,?)", [
        ("OUT-20260519-001","W1","電商平台A","COMPLETED","2026-05-19T13:00:00","W1-OP"),
        ("OUT-20260521-001","W2","電商平台B","COMPLETED","2026-05-21T14:00:00","W2-OP"),
        # OUT-20260522-001：P005 揀貨時發現少 5 個 → 產生內部問題帳
        ("OUT-20260522-001","W3","電商平台C","PICKING",  "2026-05-22T10:00:00","W3-OP"),
    ])
    c.executemany(
        "INSERT INTO outbound_order_details(order_id,sku,qty_ordered,qty_picked,shortage_qty) VALUES (?,?,?,?,?)",
        [
            ("OUT-20260519-001","P001",50,50,0),
            ("OUT-20260521-001","P007",200,200,0),
            ("OUT-20260522-001","P005",100,95,5),
        ]
    )

    # ── 盤點單 ──────────────────────────────────────────────────────────────
    c.executemany("INSERT INTO cycle_counts VALUES (?,?,?,?,?,?,?)", [
        # CNT-20260520-001：W1 手動盤點，已完成，發現 P003 差異
        ("CNT-20260520-001","W1","MANUAL","W1-PICK-003","COMPLETED","2026-05-20T09:00:00","W1-OP"),
        # CNT-20260522-001：W2 排程盤點，進行中
        ("CNT-20260522-001","W2","SCHEDULED",None,"IN_PROGRESS","2026-05-22T09:00:00","system"),
    ])
    c.executemany(
        "INSERT INTO cycle_count_details(count_id,location_id,sku,qty_system,qty_actual,difference) VALUES (?,?,?,?,?,?)",
        [
            # W1-PICK-003 盤點：系統 15 個，實際數到 10 個，差異 -5
            ("CNT-20260520-001","W1-PICK-003","P003",15,10,-5),
            # W2 排程盤點尚未填入實際數量
            ("CNT-20260522-001","W2-PICK-004","P004",25,None,None),
            ("CNT-20260522-001","W2-PICK-008","P008", 5,None,None),
        ]
    )

    # ── 庫存異動紀錄 ─────────────────────────────────────────────────────────
    c.executemany(
        "INSERT INTO inventory_movements(movement_id,movement_type,from_location,to_location,sku,quantity,t_code,created_by,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        [
            # TRF-20260501-001 完成
            ("MVT-20260501-001","TRANSFER_OUT","W2-PICK-001",None,         "P001",200,"TRF-20260501-001","W2-OP","2026-05-01T10:00:00"),
            ("MVT-20260501-002","TRANSFER_IN", None,"W1-BUF-001",          "P001",200,"TRF-20260501-001","W1-OP","2026-05-01T16:00:00"),
            # TRF-20260518-001：出庫 100，到貨 90
            ("MVT-20260518-001","TRANSFER_OUT","W2-PICK-006",None,         "P006",100,"TRF-20260518-001","W2-OP","2026-05-18T11:00:00"),
            ("MVT-20260518-002","TRANSFER_IN", None,"W1-PICK-006",         "P006", 90,"TRF-20260518-001","W1-OP","2026-05-18T17:00:00"),
            # CNT-20260520-001：盤點差異調整
            ("MVT-20260520-001","COUNT_ADJ",   "W1-PICK-003",None,         "P003",  5,"CNT-20260520-001","W1-OP","2026-05-20T10:30:00"),
            ("MVT-20260520-002","ZONE_MOVE",    None,"W2-CB-COUNT-001",    "P003",  5,"CNT-20260520-001","W1-OP","2026-05-20T10:35:00"),
            # P010 損毀移入 PROBLEM → CB-DAMAGE → DISUSE
            ("MVT-20260522-001","ZONE_MOVE",   "W1-PICK-010","W1-PROB-001","P010",  3,"CLM-20260522-002","W1-OP","2026-05-22T09:00:00"),
            ("MVT-20260522-002","ZONE_MOVE",   "W1-PROB-001","W1-CB-DAMAGE-001","P010",3,"CLM-20260522-002","W1-OP","2026-05-22T14:00:00"),
            # P006 W3 排程廢棄
            ("MVT-20260522-003","ZONE_MOVE",   "W3-PICK-006","W3-DISU-001","P006",  4,"CLM-20260519-003","W3-OP","2026-05-22T11:00:00"),
        ]
    )

    # ── 異議單 ──────────────────────────────────────────────────────────────
    c.executemany(
        "INSERT INTO claims VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            # 跨倉 Claim：W2→W1 調撥 P006 短少 10
            (
                "CLM-20260518-001","TRF-20260518-001","MVT-20260518-002",
                "TRANSFER_SHORTAGE","W1","W2","W1","ORIGIN_WH",
                10,0,"PENDING",None,"2026-05-18T17:30:00"
            ),
            # 內部問題帳：W1 盤點 P003 差異 5
            (
                "CLM-20260520-001","CNT-20260520-001","MVT-20260520-001",
                "COUNT_DISCREPANCY","W1","W1","W1","SELF",
                5,0,"IN_COLLECT_BUFFER",None,"2026-05-20T10:40:00"
            ),
            # 內部問題帳：W2 進貨 P003 短少 8
            (
                "CLM-20260515-002","INB-20260515-001",None,
                "INBOUND_SHORTAGE","W2","W2","W2","SUPPLIER",
                8,0,"INVESTIGATING",None,"2026-05-15T11:00:00"
            ),
            # 內部問題帳：W1 P010 損毀 3 個
            (
                "CLM-20260522-002","MVT-20260522-001","MVT-20260522-001",
                "DAMAGE","W1","W1","W1","SELF",
                3,0,"IN_COLLECT_BUFFER",None,"2026-05-22T09:10:00"
            ),
            # 內部問題帳：W3 出貨 P005 揀貨短少 5
            (
                "CLM-20260522-003","OUT-20260522-001",None,
                "PICKING_SHORTAGE","W3","W3","W3","SELF",
                5,0,"PENDING",None,"2026-05-22T10:30:00"
            ),
            # 內部問題帳：W3 P006 待除帳 4 個（DISUSE_PENDING）
            (
                "CLM-20260519-003","MVT-20260522-003","MVT-20260522-003",
                "DAMAGE","W3","W3","W3","SELF",
                4,0,"DISUSE_PENDING",None,"2026-05-19T08:00:00"
            ),
        ]
    )

    # ── Claim 操作紀錄 ───────────────────────────────────────────────────────
    c.executemany(
        "INSERT INTO claim_logs(claim_id,action,actor,note,timestamp) VALUES (?,?,?,?,?)",
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

    # ── 審批（除帳申請）──────────────────────────────────────────────────────
    c.execute(
        "INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?)",
        ("APV-20260522-001","WRITEOFF","CLM-20260519-003","PENDING",
         None, None,"W3 P006 損毀 4 個，待主管核准除帳","2026-05-22T11:10:00")
    )

    conn.commit()
    conn.close()


# ── Helper ────────────────────────────────────────────────────────────────────

def get_warehouse_inventory_summary():
    """各倉庫可用庫存彙總（PICKING + BUFFER 合計，AVAILABLE only）"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT sl.warehouse_id, i.sku, p.name, p.unit, p.safety_stock,
               SUM(i.quantity) AS total_qty
        FROM inventory i
        JOIN storage_locations sl ON i.location_id = sl.location_id
        JOIN products p ON i.sku = p.sku
        WHERE sl.zone_type IN ('PICKING','BUFFER')
          AND i.acct_status = 'AVAILABLE'
        GROUP BY sl.warehouse_id, i.sku
        ORDER BY sl.warehouse_id, i.sku
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_problem_stock_summary():
    """問題品、集貨緩衝、廢棄品區的庫存彙總"""
    conn = get_conn()
    rows = conn.execute("""
        SELECT sl.warehouse_id, sl.zone_type, sl.cb_category,
               i.sku, p.name, p.unit,
               SUM(i.quantity) AS quantity, i.acct_status
        FROM inventory i
        JOIN storage_locations sl ON i.location_id = sl.location_id
        JOIN products p ON i.sku = p.sku
        WHERE sl.zone_type IN ('PROBLEM','COLLECT_BUFFER','DISUSE')
          AND i.quantity > 0
        GROUP BY sl.warehouse_id, sl.zone_type, sl.cb_category, i.sku, i.acct_status
        ORDER BY sl.warehouse_id, sl.zone_type
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Startup ───────────────────────────────────────────────────────────────────

def ensure_ready():
    """Railway 啟動時呼叫：DB 不存在或資料為空則初始化。"""
    init_db()
    conn = get_conn()
    has_data = conn.execute("SELECT 1 FROM warehouses LIMIT 1").fetchone()
    conn.close()
    if not has_data:
        seed_data()
