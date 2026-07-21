from db import fetch_one, fetch_all
from datetime import datetime, date


class ReportService:

    # ================= SUMMARY =================
    def summary(self, store_id, start_date=None, end_date=None):
        query = """
            SELECT
                COALESCE(SUM(dt.qty * dt.harga), 0) AS omzet,
                COALESCE(SUM(dt.qty * COALESCE(dt.harga_modal, 0)), 0) AS modal,
                COUNT(DISTINCT t.id) AS jumlah_transaksi
            FROM transaksi t
            JOIN detail_transaksi dt ON dt.transaksi_id = t.id
            WHERE t.store_id = %s
        """
        params = [store_id]

        if start_date:
            query += " AND t.tanggal >= %s"
            params.append(start_date)

        if end_date:
            query += " AND t.tanggal <= %s"
            params.append(end_date + " 23:59:59")

        row = fetch_one(query, params)

        omzet = row["omzet"]
        modal = row["modal"]
        laba = omzet - modal

        return {
            "omzet": omzet,
            "modal": modal,
            "laba": laba,
            "jumlah_transaksi": row["jumlah_transaksi"],
        }

    # ================= PRODUK TERLARIS =================
    def produk_terlaris(self, store_id, start_date=None, end_date=None, limit=5):
        query = """
            SELECT 
                p.nama_produk,
                SUM(dt.qty) AS total_qty,
                SUM(dt.subtotal) AS total_omzet
            FROM detail_transaksi dt
            JOIN transaksi t ON t.id = dt.transaksi_id
            LEFT JOIN produk p ON p.id = dt.produk_id
            WHERE t.store_id = %s
        """
        params = [store_id]

        if start_date:
            query += " AND t.tanggal >= %s"
            params.append(start_date)

        if end_date:
            query += " AND t.tanggal <= %s"
            params.append(end_date + " 23:59:59")

        query += """
            GROUP BY dt.produk_id, p.nama_produk
            ORDER BY total_qty DESC
            LIMIT %s
        """
        params.append(limit)

        return fetch_all(query, params)

    # ================= DASHBOARD TODAY =================
    def dashboard_today(self, store_id):
        today = date.today()

        # omzet & transaksi hari ini
        row_today = fetch_one("""
            SELECT 
                COALESCE(SUM(total), 0) AS omzet,
                COUNT(*) AS jumlah
            FROM transaksi
            WHERE store_id = %s
              AND DATE(tanggal) = %s
        """, (store_id, today))

        # produk stok minim
        row_stock = fetch_one("""
            SELECT COUNT(*) AS total
            FROM produk
            WHERE store_id = %s
              AND stok <= stok_minim
        """, (store_id,))

        return {
            "omzet_hari_ini": row_today["omzet"],
            "transaksi_hari_ini": row_today["jumlah"],
            "produk_stok_minim": row_stock["total"],
        }