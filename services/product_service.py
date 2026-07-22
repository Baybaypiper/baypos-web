from db import fetch_one, fetch_all, execute, get_cursor
from datetime import datetime


class ProductService:

    # ================= GET ALL =================
    def get_all(self, store_id):
        return fetch_all("""
            SELECT 
                p.id,
                p.nama_produk,
                p.harga,
                p.harga_modal,
                p.stok,
                p.stok_minim,
                p.satuan,
                p.gambar,
                p.kategori_id,
                k.nama AS kategori_nama
            FROM produk p
            LEFT JOIN kategori k ON k.id = p.kategori_id
            WHERE p.store_id = %s
            ORDER BY p.nama_produk ASC
        """, (store_id,))

    # ================= SEARCH =================
    def search(self, store_id, keyword):
        keyword = f"%{keyword.lower()}%"

        return fetch_all("""
            SELECT 
                p.id,
                p.nama_produk,
                p.harga,
                p.harga_modal,
                p.stok,
                p.stok_minim,
                p.satuan,
                p.gambar,
                p.kategori_id,
                k.nama AS kategori_nama
            FROM produk p
            LEFT JOIN kategori k ON k.id = p.kategori_id
            WHERE p.store_id = %s 
              AND LOWER(p.nama_produk) LIKE %s
            ORDER BY p.nama_produk ASC
        """, (store_id, keyword))

    # ================= GET BY ID =================
    def get_by_id(self, product_id, store_id):
        return fetch_one("""
            SELECT *
            FROM produk
            WHERE id = %s AND store_id = %s
        """, (product_id, store_id))

    # ================= LOW STOCK =================
    def get_low_stock(self, store_id):
        return fetch_all("""
            SELECT id, nama_produk, stok, stok_minim
            FROM produk
            WHERE store_id = %s
              AND stok <= stok_minim
            ORDER BY stok ASC
        """, (store_id,))

    # ================= CREATE =================
    def create(self, store_id, nama, harga, harga_modal=0, stok=0,
               stok_minim=5, satuan="pcs", gambar=None, kategori_id=None):

        if not nama or not nama.strip():
            raise ValueError("Nama produk wajib diisi")

        if harga is None or float(harga) < 0:
            raise ValueError("Harga tidak valid")

        with get_cursor(commit=True) as cur:
            cur.execute("""
                INSERT INTO produk
                (store_id, nama_produk, harga, harga_modal, stok, stok_minim,
                 satuan, gambar, kategori_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                store_id,
                nama.strip(),
                float(harga),
                float(harga_modal),
                float(stok),
                float(stok_minim),
                satuan,
                gambar,
                kategori_id,
                datetime.utcnow()
            ))
            return cur.fetchone()["id"]

    # ================= UPDATE =================
    def update(self, product_id, store_id, nama, harga, harga_modal=0,
               stok=0, stok_minim=5, satuan="pcs", gambar=None, kategori_id=None):

        execute("""
            UPDATE produk
            SET 
                nama_produk = %s,
                harga = %s,
                harga_modal = %s,
                stok = %s,
                stok_minim = %s,
                satuan = %s,
                gambar = %s,
                kategori_id = %s
            WHERE id = %s AND store_id = %s
        """, (
            nama.strip(),
            float(harga),
            float(harga_modal),
            float(stok),
            float(stok_minim),
            satuan,
            gambar,
            kategori_id,
            product_id,
            store_id
        ))

    # ================= DELETE =================
    def delete(self, product_id, store_id):
        execute("""
            DELETE FROM produk
            WHERE id = %s AND store_id = %s
        """, (product_id, store_id))

    # ================= LIST KATEGORI =================
    def list_kategori(self):
        return fetch_all("""
            SELECT id, nama, parent
            FROM kategori
            ORDER BY parent, nama
        """)