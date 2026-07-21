import os
import sqlite3
import psycopg2
import psycopg2.extras
import hashlib
import secrets
from datetime import datetime

# ================= CONFIG =================
DATABASE_URL = os.getenv("DATABASE_URL")

# Fix Railway format
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

DB_PATH = os.path.join(os.getcwd(), "database.db")


# ================= PG WRAPPER =================
class _PGCursorWrapper:
    def __init__(self, cursor):
        self._cursor = cursor

    def execute(self, sql, params=None):
        sql = qmark(sql, self._cursor.connection)
        if params is None:
            return self._cursor.execute(sql)
        return self._cursor.execute(sql, params)

    def executemany(self, sql, seq_of_params):
        return self._cursor.executemany(
            qmark(sql, self._cursor.connection),
            seq_of_params
        )

    def __getattr__(self, name):
        return getattr(self._cursor, name)

    def __iter__(self):
        return iter(self._cursor)


class _PGConnWrapper:
    def __init__(self, conn):
        self._conn = conn

    def cursor(self, *args, **kwargs):
        kwargs.setdefault("cursor_factory", psycopg2.extras.RealDictCursor)
        return _PGCursorWrapper(self._conn.cursor(*args, **kwargs))

    def __getattr__(self, name):
        return getattr(self._conn, name)


# ================= CONNECT =================
def connect():
    if DATABASE_URL:
        print("✅ Using PostgreSQL")

        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return _PGConnWrapper(conn)

    print("⚠️ Using SQLite")

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")

    return conn


# ================= HELPER =================
def is_postgres(conn):
    return hasattr(conn, "_conn")


def qmark(sql, conn=None):
    if conn and hasattr(conn, "_conn"):
        return sql.replace("?", "%s")
    return sql


# ================= INIT =================
def init_db():
    try:
        conn = connect()
        c = conn.cursor()

        create_meta(c)
        version = get_db_version(c)

        create_tables(c)
        run_migrations(c, version)
        seed_all(c)

        conn.commit()
        conn.close()

        print("✅ DB INIT SUCCESS")

    except Exception as e:
        print("❌ DB INIT ERROR:", e)


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
        c.execute(qmark("CREATE INDEX IF NOT EXISTS idx_produk_store ON produk(store_id)"))
        c.execute(qmark("CREATE INDEX IF NOT EXISTS idx_transaksi_store ON transaksi(store_id)"))
        set_db_version(c, 1)

    if version < 5:
        c.execute(qmark("CREATE INDEX IF NOT EXISTS idx_mutasi_produk ON stok_mutasi(produk_id)"))
        set_db_version(c, 5)


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
    c.execute(qmark("SELECT id FROM stores WHERE id=?"), (1,))
    if not c.fetchone():
        c.execute(qmark("INSERT INTO stores (name, owner_id) VALUES (?, ?)"), ("Toko Utama", 1))


def seed_user(c):
    c.execute(qmark("SELECT id FROM users WHERE username=?"), ("admin",))
    if not c.fetchone():
        print("🔥 Seeding admin...")
        h, salt = hash_password("123")
        c.execute(qmark("""
        INSERT INTO users (username, password, password_salt, role, store_id)
        VALUES (?, ?, ?, 'owner', 1)
        """), ("admin", h, salt))


def seed_kategori(c):
    c.execute(qmark("SELECT COUNT(*) FROM kategori"))
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