from database import connect
from datetime import datetime


class ProductService:

    def get_all(self, store_id):
        conn = connect()
        c = conn.cursor()
        c.execute("""
            SELECT p.id, p.nama_produk, p.harga, p.harga_modal, p.stok, p.stok_minim,
                   p.satuan, p.gambar, p.kategori_id, k.nama as kategori_nama
            FROM produk p
            LEFT JOIN kategori k ON k.id = p.kategori_id
            WHERE p.store_id=?
            ORDER BY p.nama_produk ASC
        """, (store_id,))
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def search(self, store_id, keyword):
        conn = connect()
        c = conn.cursor()
        keyword = f"%{keyword.lower()}%"
        c.execute("""
            SELECT p.id, p.nama_produk, p.harga, p.harga_modal, p.stok, p.stok_minim,
                   p.satuan, p.gambar, p.kategori_id, k.nama as kategori_nama
            FROM produk p
            LEFT JOIN kategori k ON k.id = p.kategori_id
            WHERE p.store_id=? AND LOWER(p.nama_produk) LIKE ?
            ORDER BY p.nama_produk ASC
        """, (store_id, keyword))
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def get_by_id(self, product_id, store_id):
        conn = connect()
        c = conn.cursor()
        c.execute("""
            SELECT * FROM produk WHERE id=? AND store_id=?
        """, (product_id, store_id))
        row = c.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_low_stock(self, store_id):
        conn = connect()
        c = conn.cursor()
        c.execute("""
            SELECT id, nama_produk, stok, stok_minim
            FROM produk
            WHERE store_id=? AND stok <= stok_minim
            ORDER BY stok ASC
        """, (store_id,))
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def create(self, store_id, nama, harga, harga_modal=0, stok=0,
               stok_minim=5, satuan="pcs", gambar=None, kategori_id=None):
        if not nama or not nama.strip():
            raise ValueError("Nama produk wajib diisi")
        if harga is None or float(harga) < 0:
            raise ValueError("Harga tidak valid")

        conn = connect()
        c = conn.cursor()
        c.execute("""
            INSERT INTO produk
            (store_id, nama_produk, harga, harga_modal, stok, stok_minim,
             satuan, gambar, kategori_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            store_id, nama.strip(), float(harga), float(harga_modal), float(stok),
            float(stok_minim), satuan, gambar, kategori_id,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        conn.commit()
        new_id = c.lastrowid
        conn.close()
        return new_id

    def update(self, product_id, store_id, nama, harga, harga_modal=0,
               stok=0, stok_minim=5, satuan="pcs", gambar=None, kategori_id=None):
        conn = connect()
        c = conn.cursor()
        c.execute("""
            UPDATE produk
            SET nama_produk=?, harga=?, harga_modal=?, stok=?, stok_minim=?,
                satuan=?, gambar=?, kategori_id=?
            WHERE id=? AND store_id=?
        """, (
            nama.strip(), float(harga), float(harga_modal), float(stok),
            float(stok_minim), satuan, gambar, kategori_id, product_id, store_id
        ))
        conn.commit()
        conn.close()

    def delete(self, product_id, store_id):
        conn = connect()
        c = conn.cursor()
        c.execute("DELETE FROM produk WHERE id=? AND store_id=?", (product_id, store_id))
        conn.commit()
        conn.close()

    def list_kategori(self):
        conn = connect()
        c = conn.cursor()
        c.execute("SELECT id, nama, parent FROM kategori ORDER BY parent, nama")
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows