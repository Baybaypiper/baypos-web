from db import get_cursor, fetch_one, fetch_all
from datetime import datetime


class TransactionService:

    # ================= CREATE TRANSACTION =================
    def create_transaction(self, cart, user_id, store_id, payment, metode="Cash"):

        if not cart:
            raise ValueError("Keranjang kosong")

        with get_cursor(commit=True) as cur:

            total = 0
            items_detail = []

            # 🔒 LOCK semua produk yang dipakai (anti race condition)
            for item in cart:
                product_id = item["product_id"]
                qty = float(item["qty"])

                if qty <= 0:
                    raise ValueError("Qty tidak valid")

                cur.execute("""
                    SELECT harga, harga_modal, stok, nama_produk
                    FROM produk
                    WHERE id = %s AND store_id = %s
                    FOR UPDATE
                """, (product_id, store_id))

                p = cur.fetchone()

                if not p:
                    raise ValueError(f"Produk ID {product_id} tidak ditemukan")

                if float(p["stok"]) < qty:
                    raise ValueError(f"Stok tidak cukup untuk {p['nama_produk']}")

                subtotal = float(p["harga"]) * qty
                total += subtotal

                items_detail.append({
                    "product_id": product_id,
                    "nama": p["nama_produk"],
                    "qty": qty,
                    "harga": float(p["harga"]),
                    "harga_modal": float(p["harga_modal"] or 0),
                    "subtotal": subtotal,
                })

            if float(payment) < total:
                raise ValueError("Pembayaran kurang dari total")

            kembalian = float(payment) - total
            tanggal = datetime.utcnow()

            # ✅ insert transaksi (PostgreSQL way)
            cur.execute("""
                INSERT INTO transaksi
                (store_id, user_id, tanggal, total, bayar, kembalian, metode)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (store_id, user_id, tanggal, total, payment, kembalian, metode))

            trx_id = cur.fetchone()["id"]

            # insert detail + update stok + mutasi
            for item in items_detail:

                # detail transaksi
                cur.execute("""
                    INSERT INTO detail_transaksi
                    (transaksi_id, produk_id, qty, harga, harga_modal, subtotal)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    trx_id,
                    item["product_id"],
                    item["qty"],
                    item["harga"],
                    item["harga_modal"],
                    item["subtotal"]
                ))

                # update stok
                cur.execute("""
                    UPDATE produk
                    SET stok = stok - %s
                    WHERE id = %s AND store_id = %s
                """, (
                    item["qty"],
                    item["product_id"],
                    store_id
                ))

                # mutasi stok
                cur.execute("""
                    INSERT INTO stok_mutasi
                    (produk_id, store_id, tipe, qty, keterangan, user_id, tanggal)
                    VALUES (%s, %s, 'penjualan', %s, %s, %s, %s)
                """, (
                    item["product_id"],
                    store_id,
                    -item["qty"],
                    f"Terjual di transaksi #{trx_id}",
                    user_id,
                    tanggal
                ))

            return {
                "id": trx_id,
                "total": total,
                "bayar": payment,
                "kembalian": kembalian,
                "items": items_detail,
                "tanggal": tanggal,
            }

    # ================= GET ALL =================
    def get_all(self, store_id, start_date=None, end_date=None):

        query = """
            SELECT id, total, bayar, kembalian, metode, tanggal
            FROM transaksi
            WHERE store_id = %s
        """
        params = [store_id]

        if start_date:
            query += " AND DATE(tanggal) >= %s"
            params.append(start_date)

        if end_date:
            query += " AND DATE(tanggal) <= %s"
            params.append(end_date)

        query += " ORDER BY id DESC"

        return fetch_all(query, params)

    # ================= GET DETAIL =================
    def get_detail(self, trx_id, store_id):

        trx = fetch_one("""
            SELECT *
            FROM transaksi
            WHERE id = %s AND store_id = %s
        """, (trx_id, store_id))

        if not trx:
            return None

        items = fetch_all("""
            SELECT 
                dt.*,
                p.nama_produk
            FROM detail_transaksi dt
            LEFT JOIN produk p ON p.id = dt.produk_id
            WHERE dt.transaksi_id = %s
        """, (trx_id,))

        trx["items"] = items
        return trx