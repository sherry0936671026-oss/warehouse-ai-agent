import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "warehouse_agent.db")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS warehouses (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            location TEXT NOT NULL,
            capacity INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            warehouse_id TEXT NOT NULL,
            sku TEXT NOT NULL,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            safety_stock INTEGER NOT NULL DEFAULT 0,
            unit TEXT NOT NULL,
            FOREIGN KEY (warehouse_id) REFERENCES warehouses(id)
        );
        CREATE TABLE IF NOT EXISTS claims (
            id TEXT PRIMARY KEY,
            source_wh TEXT NOT NULL,
            target_wh TEXT NOT NULL,
            sku TEXT NOT NULL,
            qty INTEGER NOT NULL,
            reason TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS transfer_records (
            id TEXT PRIMARY KEY,
            from_wh TEXT NOT NULL,
            to_wh TEXT NOT NULL,
            sku TEXT NOT NULL,
            qty INTEGER NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


def seed_data():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        DELETE FROM transfer_records;
        DELETE FROM claims;
        DELETE FROM inventory;
        DELETE FROM warehouses;
    """)

    c.executemany("INSERT INTO warehouses VALUES (?,?,?,?)", [
        ("W1", "北區倉", "台北", 10000),
        ("W2", "中區倉", "台中", 8000),
        ("W3", "南區倉", "高雄", 12000),
    ])

    c.executemany(
        "INSERT INTO inventory (warehouse_id,sku,product_name,quantity,safety_stock,unit) VALUES (?,?,?,?,?,?)",
        [
            ("W1","P001","包裝紙箱(大)", 120,200,"個"),
            ("W2","P001","包裝紙箱(大)", 850,200,"個"),
            ("W3","P001","包裝紙箱(大)",  60,200,"個"),
            ("W1","P002","包裝紙箱(小)", 300,150,"個"),
            ("W2","P002","包裝紙箱(小)", 420,150,"個"),
            ("W3","P002","包裝紙箱(小)",  90,150,"個"),
            ("W1","P003","氣泡紙",        50, 80,"捲"),
            ("W2","P003","氣泡紙",       180, 80,"捲"),
            ("W3","P003","氣泡紙",        25, 80,"捲"),
            ("W1","P004","棧板",         200,100,"片"),
            ("W2","P004","棧板",          80,100,"片"),
            ("W3","P004","棧板",         350,100,"片"),
            ("W1","P005","封箱膠帶",     600,300,"捲"),
            ("W2","P005","封箱膠帶",     150,300,"捲"),
            ("W3","P005","封箱膠帶",     820,300,"捲"),
            ("W1","P006","防撞角條",      40,100,"條"),
            ("W2","P006","防撞角條",     220,100,"條"),
            ("W3","P006","防撞角條",      35,100,"條"),
            ("W1","P007","標籤貼紙",    1200,500,"張"),
            ("W2","P007","標籤貼紙",     480,500,"張"),
            ("W3","P007","標籤貼紙",    2100,500,"張"),
            ("W1","P008","棉繩",          90, 50,"捆"),
            ("W2","P008","棉繩",          15, 50,"捆"),
            ("W3","P008","棉繩",         130, 50,"捆"),
            ("W1","P009","防潮袋",       320,200,"個"),
            ("W2","P009","防潮袋",        60,200,"個"),
            ("W3","P009","防潮袋",       410,200,"個"),
            ("W1","P010","保麗龍內襯",    75,120,"片"),
            ("W2","P010","保麗龍內襯",   280,120,"片"),
            ("W3","P010","保麗龍內襯",    30,120,"片"),
        ]
    )

    c.executemany("INSERT INTO claims VALUES (?,?,?,?,?,?,?,?)", [
        ("CLM001","W1","W2","P001",100,"短送",      "待審查","2026-05-01"),
        ("CLM002","W3","W1","P003", 50,"品質異常",   "異議中","2026-05-10"),
        ("CLM003","W2","W3","P006", 30,"規格不符",   "待審查","2026-05-12"),
        ("CLM004","W1","W3","P009", 80,"短送",      "已結案","2026-04-20"),
        ("CLM005","W3","W2","P005",200,"包裝破損",   "異議中","2026-05-14"),
        ("CLM006","W2","W1","P002", 60,"短送",      "待審查","2026-05-15"),
        ("CLM007","W1","W2","P010", 40,"品質異常",   "已拒絕","2026-04-25"),
        ("CLM008","W3","W1","P004", 25,"數量溢送",   "已結案","2026-04-18"),
        ("CLM009","W2","W3","P007",300,"短送",      "異議中","2026-05-13"),
        ("CLM010","W1","W3","P008", 20,"品質異常",   "待審查","2026-05-16"),
        ("CLM011","W3","W2","P001", 90,"規格不符",   "待審查","2026-05-17"),
        ("CLM012","W2","W1","P003", 15,"包裝破損",   "異議中","2026-05-11"),
        ("CLM013","W1","W2","P005",150,"短送",      "已結案","2026-04-22"),
        ("CLM014","W3","W1","P002", 70,"品質異常",   "待審查","2026-05-18"),
        ("CLM015","W2","W3","P004", 45,"短送",      "已拒絕","2026-04-28"),
        ("CLM016","W1","W3","P007",500,"數量溢送",   "已結案","2026-04-15"),
        ("CLM017","W3","W2","P009", 55,"規格不符",   "異議中","2026-05-09"),
        ("CLM018","W2","W1","P010", 10,"包裝破損",   "待審查","2026-05-19"),
        ("CLM019","W1","W2","P006", 80,"短送",      "異議中","2026-05-08"),
        ("CLM020","W3","W1","P008", 35,"品質異常",   "待審查","2026-05-20"),
    ])

    c.executemany("INSERT INTO transfer_records VALUES (?,?,?,?,?,?,?)", [
        ("TRF001","W2","W1","P001",200,"已完成","2026-04-28"),
        ("TRF002","W2","W3","P001",100,"運送中","2026-05-15"),
        ("TRF003","W3","W1","P003", 60,"已完成","2026-04-30"),
        ("TRF004","W2","W1","P006",100,"待出庫","2026-05-20"),
        ("TRF005","W3","W2","P004",150,"已完成","2026-04-25"),
        ("TRF006","W1","W3","P007",600,"運送中","2026-05-16"),
        ("TRF007","W2","W3","P005",200,"已完成","2026-05-02"),
        ("TRF008","W3","W1","P009",120,"待出庫","2026-05-19"),
        ("TRF009","W2","W1","P002",150,"已完成","2026-05-05"),
        ("TRF010","W3","W2","P010", 80,"運送中","2026-05-17"),
        ("TRF011","W2","W3","P008", 40,"已完成","2026-05-08"),
        ("TRF012","W1","W2","P004", 50,"待出庫","2026-05-21"),
        ("TRF013","W3","W1","P006", 60,"已完成","2026-05-03"),
        ("TRF014","W2","W1","P009", 80,"運送中","2026-05-18"),
        ("TRF015","W1","W3","P002",100,"已完成","2026-05-10"),
    ])

    conn.commit()
    conn.close()


def ensure_ready():
    """初始化 DB（若尚未存在）。"""
    if not os.path.exists(DB_PATH):
        init_db()
        seed_data()
