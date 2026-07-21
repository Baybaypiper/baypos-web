import os
import psycopg2
from psycopg2 import pool, extras
from contextlib import contextmanager
import hashlib
import secrets
from datetime import datetime

# ================= CONFIG =================
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is required (PostgreSQL only)")

if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


# ================= CONNECTION POOL =================
connection_pool = psycopg2.pool.SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    dsn=DATABASE_URL
)


def get_conn():
    return connection_pool.getconn()


def release_conn(conn):
    connection_pool.putconn(conn)


@contextmanager
def get_cursor(commit=False):
    conn = get_conn()
    cur = conn.cursor(cursor_factory=extras.RealDictCursor)
    try:
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        release_conn(conn)


# ================= QUERY HELPERS =================
def fetch_one(query, params=None):
    with get_cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchone()


def fetch_all(query, params=None):
    with get_cursor() as cur:
        cur.execute(query, params or ())
        return cur.fetchall()


def execute(query, params=None):
    with get_cursor(commit=True) as cur:
        cur.execute(query, params or ())


def executemany(query, params_list):
    with get_cursor(commit=True) as cur:
        cur.executemany(query, params_list)


# ================= INIT =================
def init_db():
    try:
        create_meta()
        version = get_db_version()

        create_tables()
        run_migrations(version)
        seed_all()

        print("✅ DB INIT SUCCESS")

    except Exception as e:
        print("❌ DB INIT ERROR:", e)
        raise


# ================= META =================
def create_meta():
    execute("""
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)


def get_db_version():
    row = fetch_one("SELECT value FROM meta WHERE key = %s", ("db_version",))

    if row:
        return int(row["value"])

    execute(
        "INSERT INTO meta (key, value) VALUES (%s, %s)",
        ("db_version", "0")
    )
    return 0


def set_db_version(version):
    execute(
        "UPDATE meta SET value = %s WHERE key = %s",
        (str(version), "db_version")
    )


# ================= TABLES =================
def create_tables():
    execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            password_salt TEXT,
            role TEXT,
            store_id INTEGER,
            token TEXT,
            created_at TIMESTAMP,
            last_login TIMESTAMP
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS stores (
            id SERIAL PRIMARY KEY,
            name TEXT,
            owner_id INTEGER
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS kategori (
            id SERIAL PRIMARY KEY,
            nama TEXT,
            parent TEXT
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS produk (
            id SERIAL PRIMARY KEY,
            store_id INTEGER,
            nama_produk TEXT,
            harga NUMERIC,
            harga_modal NUMERIC DEFAULT 0,
            stok NUMERIC DEFAULT 0,
            stok_minim NUMERIC DEFAULT 5,
            satuan TEXT,
            gambar TEXT,
            kategori_id INTEGER,
            favorit INTEGER DEFAULT 0,
            created_at TIMESTAMP
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS transaksi (
            id SERIAL PRIMARY KEY,
            store_id INTEGER,
            user_id INTEGER,
            tanggal TIMESTAMP,
            total NUMERIC,
            bayar NUMERIC,
            kembalian NUMERIC,
            metode TEXT
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS detail_transaksi (
            id SERIAL PRIMARY KEY,
            transaksi_id INTEGER,
            produk_id INTEGER,
            qty NUMERIC,
            harga NUMERIC,
            harga_modal NUMERIC DEFAULT 0,
            subtotal NUMERIC
        )
    """)

    execute("""
        CREATE TABLE IF NOT EXISTS stok_mutasi (
            id SERIAL PRIMARY KEY,
            produk_id INTEGER,
            store_id INTEGER,
            tipe TEXT,
            qty NUMERIC,
            keterangan TEXT,
            user_id INTEGER,
            tanggal TIMESTAMP
        )
    """)


# ================= MIGRATIONS =================
def run_migrations(version):
    if version < 1:
        execute("CREATE INDEX IF NOT EXISTS idx_produk_store ON produk(store_id)")
        execute("CREATE INDEX IF NOT EXISTS idx_transaksi_store ON transaksi(store_id)")
        set_db_version(1)

    if version < 5:
        execute("CREATE INDEX IF NOT EXISTS idx_mutasi_produk ON stok_mutasi(produk_id)")
        set_db_version(5)


# ================= PASSWORD =================
def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)

    hashed = hashlib.sha256((salt + password).encode()).hexdigest()
    return hashed, salt


def hash_password_legacy(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ================= SEED =================
def seed_all():
    seed_store()
    seed_user()
    seed_kategori()


def seed_store():
    row = fetch_one("SELECT id FROM stores WHERE id = %s", (1,))
    if not row:
        execute(
            "INSERT INTO stores (name, owner_id) VALUES (%s, %s)",
            ("Toko Utama", 1)
        )


def seed_user():
    row = fetch_one("SELECT id FROM users WHERE username = %s", ("admin",))
    if not row:
        print("🔥 Seeding admin...")
        h, salt = hash_password("123")

        execute("""
            INSERT INTO users (username, password, password_salt, role, store_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, ("admin", h, salt, "owner", 1, datetime.utcnow()))


def seed_kategori():
    row = fetch_one("SELECT COUNT(*) AS count FROM kategori")

    if row["count"] > 0:
        return

    data = [
        ("Sayur", "Grocery"),
        ("Buah", "Grocery"),
        ("Daging", "Grocery"),
        ("Minuman", "Retail"),
        ("Snack", "Retail"),
    ]

    executemany(
        "INSERT INTO kategori (nama, parent) VALUES (%s, %s)",
        data
    )


# ================= HELPER =================
def now():
    return datetime.utcnow()