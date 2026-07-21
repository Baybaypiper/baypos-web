from db import get_cursor, fetch_one, fetch_all
from datetime import datetime


class StockService:

    # ================= ADJUST STOCK (ATOMIC) =================
    def adjust_stock(self, product_id, store_id, qty_change, tipe, keterangan, user_id):
        """
        tipe:
        - 'masuk'
        - 'keluar'
        - 'opname'
        """

        with get_cursor(commit=True) as cur:

            # 🔒 LOCK ROW (anti race condition)
            cur.execute("""
                SELECT stok, nama_produk
                FROM produk
                WHERE id = %s AND store_id = %s
                FOR UPDATE
            """, (product_id, store_id))

            p = cur.fetchone()

            if not p:
                raise ValueError("Produk tidak ditemukan")

            new_stock = float(p["stok"]) + float(qty_change)

            if new_stock < 0:
                raise ValueError(f"Stok {p['nama_produk']} tidak boleh minus")

            # update stok
            cur.execute("""
                UPDATE produk
                SET stok = %s
                WHERE id = %s AND store_id = %s
            """, (new_stock, product_id, store_id))

            # insert mutasi
            cur.execute("""
                INSERT INTO stok_mutasi
                (produk_id, store_id, tipe, qty, keterangan, user_id, tanggal)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                product_id,
                store_id,
                tipe,
                float(qty_change),
                keterangan,
                user_id,
                datetime.utcnow()
            ))

            return new_stock

    # ================= STOCK OPNAME =================
    def set_stock_opname(self, product_id, store_id, actual_qty, user_id, keterangan="Stok opname"):

        p = fetch_one("""
            SELECT stok
            FROM produk
            WHERE id = %s AND store_id = %s
        """, (product_id, store_id))

        if not p:
            raise ValueError("Produk tidak ditemukan")

        selisih = float(actual_qty) - float(p["stok"])

        return self.adjust_stock(
            product_id,
            store_id,
            selisih,
            "opname",
            keterangan,
            user_id
        )

    # ================= GET MUTASI =================
    def get_mutasi(self, store_id, product_id=None, limit=100):

        query = """
            SELECT 
                m.*,
                p.nama_produk
            FROM stok_mutasi m
            LEFT JOIN produk p ON p.id = m.produk_id
            WHERE m.store_id = %s
        """
        params = [store_id]

        if product_id:
            query += " AND m.produk_id = %s"
            params.append(product_id)

        query += " ORDER BY m.id DESC LIMIT %s"
        params.append(limit)

        return fetch_all(query, params)