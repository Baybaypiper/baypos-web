from database import connect
from datetime import datetime


class TransactionService:

    def create_transaction(self, cart, user_id, store_id, payment, metode="Cash"):
        """
        cart = [{"product_id": 1, "qty": 2}, ...]

        Semua langkah (cek stok, insert transaksi, insert detail,
        kurangi stok, catat mutasi) dijalankan dalam SATU koneksi &
        SATU transaksi database -- kalau ada yang gagal di tengah,
        semuanya di-rollback. Ini memperbaiki bug lama di mana stok
        bisa berkurang meski transaksi gagal tercatat (atau sebaliknya).
        """
        if not cart:
            raise ValueError("Keranjang kosong")

        conn = connect()
        c = conn.cursor()

        try:
            total = 0
            items_detail = []

            for item in cart:
                product_id = item["product_id"]
                qty = float(item["qty"])

                if qty <= 0:
                    raise ValueError("Qty tidak valid")

                c.execute("""
                    SELECT harga, harga_modal, stok, nama_produk
                    FROM produk WHERE id=? AND store_id=?
                """, (product_id, store_id))
                p = c.fetchone()

                if not p:
                    raise ValueError(f"Produk ID {product_id} tidak ditemukan")

                if p["stok"] < qty:
                    raise ValueError(f"Stok tidak cukup untuk {p['nama_produk']}")

                subtotal = p["harga"] * qty
                total += subtotal

                items_detail.append({
                    "product_id": product_id,
                    "nama": p["nama_produk"],
                    "qty": qty,
                    "harga": p["harga"],
                    "harga_modal": p["harga_modal"] or 0,
                    "subtotal": subtotal,
                })

            if payment < total:
                raise ValueError("Pembayaran kurang dari total")

            kembalian = payment - total
            tanggal = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            c.execute("""
                INSERT INTO transaksi
                (store_id, user_id, tanggal, total, bayar, kembalian, metode)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (store_id, user_id, tanggal, total, payment, kembalian, metode))
            trx_id = c.lastrowid

            for item in items_detail:
                c.execute("""
                    INSERT INTO detail_transaksi
                    (transaksi_id, produk_id, qty, harga, harga_modal, subtotal)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (trx_id, item["product_id"], item["qty"], item["harga"],
                      item["harga_modal"], item["subtotal"]))

                c.execute("""
                    UPDATE produk SET stok = stok - ? WHERE id=? AND store_id=?
                """, (item["qty"], item["product_id"], store_id))

                c.execute("""
                    INSERT INTO stok_mutasi
                    (produk_id, store_id, tipe, qty, keterangan, user_id, tanggal)
                    VALUES (?, ?, 'penjualan', ?, ?, ?, ?)
                """, (item["product_id"], store_id, -item["qty"],
                      f"Terjual di transaksi #{trx_id}", user_id, tanggal))

            conn.commit()

            return {
                "id": trx_id,
                "total": total,
                "bayar": payment,
                "kembalian": kembalian,
                "items": items_detail,
                "tanggal": tanggal,
            }

        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def get_all(self, store_id, start_date=None, end_date=None):
        conn = connect()
        c = conn.cursor()

        query = """
            SELECT id, total, bayar, kembalian, metode, tanggal
            FROM transaksi WHERE store_id=?
        """
        params = [store_id]

        if start_date:
            query += " AND date(tanggal) >= date(?)"
            params.append(start_date)
        if end_date:
            query += " AND date(tanggal) <= date(?)"
            params.append(end_date)

        query += " ORDER BY id DESC"

        c.execute(query, params)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def get_detail(self, trx_id, store_id):
        conn = connect()
        c = conn.cursor()

        c.execute("""
            SELECT * FROM transaksi WHERE id=? AND store_id=?
        """, (trx_id, store_id))
        trx = c.fetchone()

        if not trx:
            conn.close()
            return None

        c.execute("""
            SELECT dt.*, p.nama_produk
            FROM detail_transaksi dt
            LEFT JOIN produk p ON p.id = dt.produk_id
            WHERE dt.transaksi_id=?
        """, (trx_id,))
        items = [dict(r) for r in c.fetchall()]
        conn.close()

        result = dict(trx)
        result["items"] = items
        return result