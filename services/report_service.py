from database import connect


class ReportService:

    def summary(self, store_id, start_date=None, end_date=None):
        conn = connect()
        c = conn.cursor()

        query = """
            SELECT t.id, t.total, dt.qty, dt.harga, dt.harga_modal
            FROM transaksi t
            JOIN detail_transaksi dt ON dt.transaksi_id = t.id
            WHERE t.store_id=?
        """
        params = [store_id]

        if start_date:
            query += " AND date(t.tanggal) >= date(?)"
            params.append(start_date)
        if end_date:
            query += " AND date(t.tanggal) <= date(?)"
            params.append(end_date)

        c.execute(query, params)
        rows = c.fetchall()
        conn.close()

        omzet = 0
        modal = 0
        trx_ids = set()

        for r in rows:
            omzet += r["harga"] * r["qty"]
            modal += (r["harga_modal"] or 0) * r["qty"]
            trx_ids.add(r["id"])

        laba = omzet - modal

        return {
            "omzet": omzet,
            "modal": modal,
            "laba": laba,
            "jumlah_transaksi": len(trx_ids),
        }

    def produk_terlaris(self, store_id, start_date=None, end_date=None, limit=5):
        conn = connect()
        c = conn.cursor()

        query = """
            SELECT p.nama_produk, SUM(dt.qty) as total_qty, SUM(dt.subtotal) as total_omzet
            FROM detail_transaksi dt
            JOIN transaksi t ON t.id = dt.transaksi_id
            LEFT JOIN produk p ON p.id = dt.produk_id
            WHERE t.store_id=?
        """
        params = [store_id]

        if start_date:
            query += " AND date(t.tanggal) >= date(?)"
            params.append(start_date)
        if end_date:
            query += " AND date(t.tanggal) <= date(?)"
            params.append(end_date)

        query += " GROUP BY dt.produk_id ORDER BY total_qty DESC LIMIT ?"
        params.append(limit)

        c.execute(query, params)
        rows = [dict(r) for r in c.fetchall()]
        conn.close()
        return rows

    def dashboard_today(self, store_id):
        conn = connect()
        c = conn.cursor()

        c.execute("""
            SELECT COALESCE(SUM(total), 0) as omzet, COUNT(*) as jumlah
            FROM transaksi
            WHERE store_id=? AND date(tanggal) = date('now', 'localtime')
        """, (store_id,))
        today = dict(c.fetchone())

        c.execute("""
            SELECT COUNT(*) as total FROM produk
            WHERE store_id=? AND stok <= stok_minim
        """, (store_id,))
        low_stock = c.fetchone()["total"]

        conn.close()
        return {
            "omzet_hari_ini": today["omzet"],
            "transaksi_hari_ini": today["jumlah"],
            "produk_stok_minim": low_stock,
        }