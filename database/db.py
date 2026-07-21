import os
import sqlite3
import psycopg2
import hashlib
import secrets
from datetime import datetime

# ================= CONFIG =================
DATABASE_URL = os.environ.get("DATABASE_URL")

DB_PATH = os.environ.get(
    "BAYPOS_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "baypos.db")
)

# ================= CONNECT =================
def connect():
    if DATABASE_URL:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")

        return conn

# ================= HELPER =================
def is_postgres(conn):
    return conn.__class__.__module__.startswith("psycopg2")

def qmark(sql):
    """convert ? -> %s kalau postgres"""
    if DATABASE_URL:
        return sql.replace("?", "%s")
    return sql

# ================= INIT =================
def init_db():
    conn = connect()
    c = conn.cursor()

    create_meta(c)
    version = get_db_version(c)

    create_tables(c)
    run_migrations(c, version)
    seed_all(c)

    conn.commit()
    conn.close()

# ================= META =================
def create_meta(c):
    c.execute(qmark("""
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """))

def get_db_version(c):
    c.execute(qmark("SELECT value FROM meta WHERE key=?"), ("db_version",))
    row = c.fetchone()

    if row:
        return int(row[0] if isinstance(row, tuple) else row["value"])

    c.execute(qmark("INSERT INTO meta (key, value) VALUES (?, ?)"), ("db_version", "0"))
    return 0

def set_db_version(c, version):
    c.execute(qmark("UPDATE meta SET value=? WHERE key=?"), (str(version), "db_version"))

# ================= TABLES =================
def create_tables(c):

    auto_id = "SERIAL PRIMARY KEY" if DATABASE_URL else "INTEGER PRIMARY KEY AUTOINCREMENT"

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS users (
        id {auto_id},
        username TEXT UNIQUE,
        password TEXT,
        password_salt TEXT,
        role TEXT,
        store_id INTEGER
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS stores (
        id {auto_id},
        name TEXT,
        owner_id INTEGER
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS kategori (
        id {auto_id},
        nama TEXT,
        parent TEXT
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS produk (
        id {auto_id},
        store_id INTEGER,
        nama_produk TEXT,
        harga REAL,
        harga_modal REAL DEFAULT 0,
        stok REAL DEFAULT 0,
        stok_minim REAL DEFAULT 5,
        satuan TEXT,
        gambar TEXT,
        kategori_id INTEGER,
        favorit INTEGER DEFAULT 0,
        created_at TEXT
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS transaksi (
        id {auto_id},
        store_id INTEGER,
        user_id INTEGER,
        tanggal TEXT,
        total REAL,
        bayar REAL,
        kembalian REAL,
        metode TEXT
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS detail_transaksi (
        id {auto_id},
        transaksi_id INTEGER,
        produk_id INTEGER,
        qty REAL,
        harga REAL,
        harga_modal REAL DEFAULT 0,
        subtotal REAL
    )
    """)

    c.execute(f"""
    CREATE TABLE IF NOT EXISTS stok_mutasi (
        id {auto_id},
        produk_id INTEGER,
        store_id INTEGER,
        tipe TEXT,
        qty REAL,
        keterangan TEXT,
        user_id INTEGER,
        tanggal TEXT
    )
    """)

# ================= MIGRATIONS =================
def run_migrations(c, version):

    if version < 1:
        c.execute("CREATE INDEX IF NOT EXISTS idx_produk_store ON produk(store_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_transaksi_store ON transaksi(store_id)")
        set_db_version(c, 1)

    if version < 2:
        set_db_version(c, 2)

    if version < 3:
        set_db_version(c, 3)

    if version < 4:
        set_db_version(c, 4)

    if version < 5:
        c.execute("CREATE INDEX IF NOT EXISTS idx_mutasi_produk ON stok_mutasi(produk_id)")
        set_db_version(c, 5)

    if version < 6:
        set_db_version(c, 6)

# ================= PASSWORD =================
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed, salt

# ================= SEED =================
def seed_all(c):
    seed_store(c)
    seed_user(c)
    seed_kategori(c)

def seed_store(c):
    c.execute(qmark("SELECT id FROM stores WHERE id=?"), (1,))
    if not c.fetchone():
        c.execute(qmark("INSERT INTO stores (name, owner_id) VALUES (?, ?)"), ("Toko Utama", 1))

def seed_user(c):
    c.execute(qmark("SELECT id FROM users WHERE username=?"), ("admin",))
    if not c.fetchone():
        h, salt = hash_password("123")
        c.execute(qmark("""
        INSERT INTO users (username, password, password_salt, role, store_id)
        VALUES (?, ?, ?, 'owner', 1)
        """), ("admin", h, salt))

def seed_kategori(c):
    c.execute("SELECT COUNT(*) FROM kategori")
    count = c.fetchone()[0]

    if count > 0:
        return

    data = [
        ("Sayur", "Grocery"),
        ("Buah", "Grocery"),
        ("Daging", "Grocery"),
        ("Minuman", "Retail"),
        ("Snack", "Retail"),
    ]

    c.executemany(qmark("INSERT INTO kategori (nama, parent) VALUES (?, ?)"), data)

# ================= HELPER =================
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")