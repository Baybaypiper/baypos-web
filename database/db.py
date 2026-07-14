import sqlite3
import hashlib
import os
import secrets
from datetime import datetime

# ================= CONFIG =================
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "baypos.db")


# ================= CONNECT =================
def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # performance + safety
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")

    return conn


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
    c.execute("""
    CREATE TABLE IF NOT EXISTS meta (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)


def get_db_version(c):
    c.execute("SELECT value FROM meta WHERE key='db_version'")
    row = c.fetchone()

    if row:
        return int(row["value"])

    c.execute("INSERT INTO meta (key, value) VALUES ('db_version', '0')")
    return 0


def set_db_version(c, version):
    c.execute("UPDATE meta SET value=? WHERE key='db_version'", (str(version),))


# ================= TABLES =================
def create_tables(c):

    # USERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        password_salt TEXT,
        role TEXT,
        store_id INTEGER
    )
    """)

    # STORES
    c.execute("""
    CREATE TABLE IF NOT EXISTS stores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        owner_id INTEGER
    )
    """)

    # KATEGORI
    c.execute("""
    CREATE TABLE IF NOT EXISTS kategori (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nama TEXT,
        parent TEXT
    )
    """)

    # PRODUK
    c.execute("""
    CREATE TABLE IF NOT EXISTS produk (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # TRANSAKSI
    c.execute("""
    CREATE TABLE IF NOT EXISTS transaksi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        store_id INTEGER,
        user_id INTEGER,
        tanggal TEXT,
        total REAL,
        bayar REAL,
        kembalian REAL,
        metode TEXT
    )
    """)

    # DETAIL TRANSAKSI
    c.execute("""
    CREATE TABLE IF NOT EXISTS detail_transaksi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        transaksi_id INTEGER,
        produk_id INTEGER,
        qty REAL,
        harga REAL,
        harga_modal REAL DEFAULT 0,
        subtotal REAL
    )
    """)

    # STOK MUTASI
    c.execute("""
    CREATE TABLE IF NOT EXISTS stok_mutasi (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # index performance
    if version < 1:
        c.execute("CREATE INDEX IF NOT EXISTS idx_produk_store ON produk(store_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_transaksi_store ON transaksi(store_id)")
        set_db_version(c, 1)

    # add created_at
    if version < 2:
        cols = get_columns(c, "produk")
        if "created_at" not in cols:
            c.execute("ALTER TABLE produk ADD COLUMN created_at TEXT")
        set_db_version(c, 2)

    # add harga_modal + stok_minim
    if version < 3:
        cols = get_columns(c, "produk")
        if "harga_modal" not in cols:
            c.execute("ALTER TABLE produk ADD COLUMN harga_modal REAL DEFAULT 0")
        if "stok_minim" not in cols:
            c.execute("ALTER TABLE produk ADD COLUMN stok_minim REAL DEFAULT 5")
        set_db_version(c, 3)

    # detail transaksi modal
    if version < 4:
        cols = get_columns(c, "detail_transaksi")
        if "harga_modal" not in cols:
            c.execute("ALTER TABLE detail_transaksi ADD COLUMN harga_modal REAL DEFAULT 0")
        set_db_version(c, 4)

    # stok mutasi
    if version < 5:
        c.execute("CREATE INDEX IF NOT EXISTS idx_mutasi_produk ON stok_mutasi(produk_id)")
        set_db_version(c, 5)

    # password salt
    if version < 6:
        cols = get_columns(c, "users")
        if "password_salt" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN password_salt TEXT")
        set_db_version(c, 6)


def get_columns(c, table):
    c.execute(f"PRAGMA table_info({table})")
    return [col[1] for col in c.fetchall()]


# ================= PASSWORD =================
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed, salt


def hash_password_legacy(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ================= SEED =================
def seed_all(c):
    seed_store(c)
    seed_user(c)
    seed_kategori(c)


def seed_store(c):
    c.execute("SELECT id FROM stores WHERE id=1")
    if not c.fetchone():
        c.execute("INSERT INTO stores (name, owner_id) VALUES ('Toko Utama', 1)")


def seed_user(c):
    c.execute("SELECT id FROM users WHERE username='admin'")
    if not c.fetchone():
        h, salt = hash_password("123")
        c.execute("""
        INSERT INTO users (username, password, password_salt, role, store_id)
        VALUES (?, ?, ?, 'owner', 1)
        """, ("admin", h, salt))


def seed_kategori(c):
    c.execute("SELECT COUNT(*) as total FROM kategori")
    if c.fetchone()["total"] > 0:
        return

    data = [
        ("Sayur", "Grocery"),
        ("Buah", "Grocery"),
        ("Daging", "Grocery"),
        ("Minuman", "Retail"),
        ("Snack", "Retail"),
    ]

    c.executemany("INSERT INTO kategori (nama, parent) VALUES (?, ?)", data)


# ================= HELPER =================
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")