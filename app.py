import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, jsonify

from database import init_db
from services.auth_service import AuthService
from services.product_service import ProductService
from services.transaction_service import TransactionService
from services.stock_service import StockService
from services.report_service import ReportService

# ================= CONFIG =================
app = Flask(__name__, static_folder="static")
app.secret_key = os.environ.get("BAYPOS_SECRET", "dev-secret-ganti")

# ================= INIT =================
auth_service = AuthService()
product_service = ProductService()
transaction_service = TransactionService()
stock_service = StockService()
report_service = ReportService()

# SAFE INIT DB (BIAR GAK CRASH DI RAILWAY)
try:
    init_db()
    print("✅ DB INIT SUCCESS")
except Exception as e:
    print("❌ DB INIT ERROR:", e)


# ================= HEALTH CHECK =================
@app.route("/healthz")
def health_check():
    return "OK", 200


# ================= AUTH HELPERS =================
def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Belum login"}), 401
            return redirect(url_for("login"))
        return f(*a, **kw)
    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*a, **kw):
            if session.get("role") not in roles:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Tidak punya akses"}), 403
                return render_template("error.html", message="Tidak punya akses"), 403
            return f(*a, **kw)
        return wrapper
    return decorator


# ================= PAGES =================
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    user = auth_service.login(username, password)
    if not user:
        return render_template("login.html", error="Username / password salah")

    session.update({
        "user_id": user["id"],
        "username": user["username"],
        "role": user["role"],
        "store_id": user["store_id"]
    })

    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def dashboard():
    return render_template("dashboard.html", active="dashboard")


@app.route("/kasir")
@login_required
def kasir():
    return render_template("kasir.html", active="kasir")


@app.route("/produk")
@login_required
@role_required("owner", "admin")
def produk():
    return render_template("produk.html", active="produk")


@app.route("/laporan")
@login_required
@role_required("owner", "admin")
def laporan():
    return render_template("laporan.html", active="laporan")


@app.route("/pengguna")
@login_required
@role_required("owner")
def pengguna():
    return render_template("pengguna.html", active="pengguna")


# ================= API: PRODUK =================
@app.route("/api/produk")
@login_required
def api_produk_list():
    store_id = session.get("store_id")
    keyword = request.args.get("q", "").strip()

    try:
        data = product_service.search(store_id, keyword) if keyword else product_service.get_all(store_id)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/produk/kategori")
@login_required
def api_kategori():
    try:
        return jsonify(product_service.list_kategori())
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/produk", methods=["POST"])
@login_required
@role_required("owner", "admin")
def api_produk_create():
    d = request.get_json(silent=True) or {}

    try:
        new_id = product_service.create(
            store_id=session.get("store_id"),
            nama=d.get("nama_produk"),
            harga=d.get("harga"),
            harga_modal=d.get("harga_modal", 0),
            stok=d.get("stok", 0),
            stok_minim=d.get("stok_minim", 5),
            satuan=d.get("satuan", "pcs"),
            gambar=d.get("gambar"),
            kategori_id=d.get("kategori_id"),
        )
        return jsonify({"id": new_id}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/produk/<int:pid>", methods=["PUT"])
@login_required
@role_required("owner", "admin")
def api_produk_update(pid):
    d = request.get_json(silent=True) or {}

    try:
        product_service.update(
            product_id=pid,
            store_id=session.get("store_id"),
            nama=d.get("nama_produk"),
            harga=d.get("harga"),
            harga_modal=d.get("harga_modal", 0),
            stok=d.get("stok", 0),
            stok_minim=d.get("stok_minim", 5),
            satuan=d.get("satuan", "pcs"),
            gambar=d.get("gambar"),
            kategori_id=d.get("kategori_id"),
        )
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/produk/<int:pid>", methods=["DELETE"])
@login_required
@role_required("owner", "admin")
def api_produk_delete(pid):
    try:
        product_service.delete(pid, session.get("store_id"))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/produk/low-stock")
@login_required
def api_low_stock():
    try:
        return jsonify(product_service.get_low_stock(session.get("store_id")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= API: STOK =================
@app.route("/api/stok/adjust", methods=["POST"])
@login_required
@role_required("owner", "admin")
def api_stok_adjust():
    d = request.get_json(silent=True) or {}

    try:
        new_stock = stock_service.adjust_stock(
            product_id=d.get("produk_id"),
            store_id=session.get("store_id"),
            qty_change=float(d.get("qty_change", 0)),
            tipe=d.get("tipe", "masuk"),
            keterangan=d.get("keterangan", ""),
            user_id=session.get("user_id"),
        )
        return jsonify({"stok_baru": new_stock})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/stok/mutasi")
@login_required
@role_required("owner", "admin")
def api_stok_mutasi():
    try:
        pid = request.args.get("produk_id", type=int)
        return jsonify(stock_service.get_mutasi(session.get("store_id"), product_id=pid))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= API: TRANSAKSI =================
@app.route("/api/checkout", methods=["POST"])
@login_required
def api_checkout():
    d = request.get_json(silent=True) or {}

    try:
        result = transaction_service.create_transaction(
            cart=d.get("cart", []),
            user_id=session.get("user_id"),
            store_id=session.get("store_id"),
            payment=float(d.get("payment", 0)),
            metode=d.get("metode", "Cash"),
        )
        return jsonify(result), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/transaksi/<int:trx_id>")
@login_required
def api_transaksi_detail(trx_id):
    try:
        result = transaction_service.get_detail(trx_id, session.get("store_id"))
        if not result:
            return jsonify({"error": "Transaksi tidak ditemukan"}), 404
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= API: LAPORAN =================
@app.route("/api/laporan")
@login_required
@role_required("owner", "admin")
def api_laporan():
    start = request.args.get("start")
    end = request.args.get("end")

    try:
        return jsonify({
            "summary": report_service.summary(session.get("store_id"), start, end),
            "transaksi": transaction_service.get_all(session.get("store_id"), start, end),
            "produk_terlaris": report_service.produk_terlaris(session.get("store_id"), start, end),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/dashboard")
@login_required
def api_dashboard():
    try:
        return jsonify(report_service.dashboard_today(session.get("store_id")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ================= API: PENGGUNA =================
@app.route("/api/pengguna")
@login_required
@role_required("owner")
def api_pengguna_list():
    try:
        return jsonify(auth_service.list_users(session.get("store_id")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/pengguna", methods=["POST"])
@login_required
@role_required("owner")
def api_pengguna_create():
    d = request.get_json(silent=True) or {}

    try:
        auth_service.register(
            username=d.get("username", "").strip(),
            password=d.get("password", ""),
            role=d.get("role", "kasir"),
            store_id=session.get("store_id"),
        )
        return jsonify({"ok": True}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/pengguna/<int:uid>", methods=["DELETE"])
@login_required
@role_required("owner")
def api_pengguna_delete(uid):
    try:
        if uid == session.get("user_id"):
            return jsonify({"error": "Tidak bisa hapus akun sendiri"}), 400

        auth_service.delete_user(uid, session.get("store_id"))
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


# ================= RUN (LOCAL ONLY) =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)