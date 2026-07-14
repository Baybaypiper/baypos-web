from database import connect
from datetime import datetime


class StockService:

    def adjust_stock(self, product_id, store_id, qty_change, tipe, keterangan, user_id):
        """
        tipe: 'masuk' (barang datang), 'keluar' (rusak/hilang), 'opname' (koreksi stok fisik)
        qty_change: boleh positif atau negatif
        """
        conn = connect()
        c = conn.cursor()

        try:
            c.execute("""
                SELECT stok, nama_produk FROM produk WHERE id=? AND store_id=?
            """, (product_id, store_id))
            p = c.fetchone()

            if not p:
                raise ValueError("Produk tidak ditemukan")

            new_stock = p["stok"] + qty_change
            if new_stock < 0:
                raise ValueError(f"Stok {p['nama_produk']} tidak boleh minus")

            c.execute("""
                UPDATE produk SET stok=? WHERE id=? AND store_id=?
            """, (new_stock, product_id, store_id))

            c.execute("""
                INSERT INTO stok_mutasi
                (produk_id, store_id, tipe, qty, keterangan, user_id, tanggal)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (product_id, store_id, tipe, qty_change, keterangan, user_id,
                  datetime.now().strftime("%Y-%m-%d %H:%M:%S")))

            conn.commit()
            return new_stock

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def set_stock_opname(self, product_id, store_id, actual_qty, user_id, keterangan="Stok opname"):
        conn = connect()
        c = conn.cursor()
        c.execute("SELECT stok FROM produk WHERE id=? AND store_id=?", (product_id, store_id))
        p = c.fetchone()
        conn.close()

        if not p:
            raise ValueError("Produk tidak ditemukan")

        selisih = actual_qty - p["stok"]
        return self.adjust_stock(product_id, store_id, selisih, "opname", keterangan, user_id)

    def get_mutasi(self, store_id, product_id=None, limit=100):
        conn = connect()
        c = conn.cursor()

        query = """
            SELECT m.*, p.nama_produk
            FROM stok_mutasi m
            LEFT JOIN produk p ON p.id = m.produk_id
            WHERE m.store_id=?
        """
        params = [store_id]

        if product_id:
            query += " AND m.produk_id=?"
            params.append(product_id)

        query += " ORDER BY m.id DESC LIMIT ?"
        params.append(limit)

        c.execute(query, params)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows