let allProducts = [];
let cart = {}; // { productId: { produk, qty } }

function rupiah(n) {
  return "Rp" + Math.round(n).toLocaleString("id-ID");
}

async function loadProducts(keyword = "") {
  const url = keyword ? `/api/produk?q=${encodeURIComponent(keyword)}` : "/api/produk";
  const res = await fetch(url);
  allProducts = await res.json();
  renderGrid();
}

function renderGrid() {
  const grid = document.getElementById("produkGrid");
  grid.innerHTML = "";

  if (allProducts.length === 0) {
    grid.innerHTML = `<p style="color:var(--text-muted);">Tidak ada produk ditemukan.</p>`;
    return;
  }

  allProducts.forEach(p => {
    const outOfStock = p.stok <= 0;
    const el = document.createElement("div");
    el.className = "produk-item" + (outOfStock ? " out-of-stock" : "");
    el.innerHTML = `
      <div class="nama">${escapeHtml(p.nama_produk)}</div>
      <div class="harga">${rupiah(p.harga)}</div>
      <div class="stok-info">Stok: ${p.stok} ${p.satuan || ""}</div>
    `;
    if (!outOfStock) {
      el.addEventListener("click", () => addToCart(p));
    }
    grid.appendChild(el);
  });
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s;
  return div.innerHTML;
}

function addToCart(p) {
  const existingQty = cart[p.id] ? cart[p.id].qty : 0;
  if (existingQty + 1 > p.stok) {
    alert(`Stok ${p.nama_produk} tidak cukup`);
    return;
  }
  if (cart[p.id]) {
    cart[p.id].qty += 1;
  } else {
    cart[p.id] = { produk: p, qty: 1 };
  }
  renderCart();
}

function changeQty(pid, delta) {
  const item = cart[pid];
  if (!item) return;

  const newQty = item.qty + delta;
  if (newQty <= 0) {
    delete cart[pid];
  } else if (newQty > item.produk.stok) {
    alert("Stok tidak cukup");
    return;
  } else {
    item.qty = newQty;
  }
  renderCart();
}

function calcTotal() {
  return Object.values(cart).reduce((sum, i) => sum + i.produk.harga * i.qty, 0);
}

function renderCart() {
  const container = document.getElementById("cartItems");
  const items = Object.entries(cart);

  if (items.length === 0) {
    container.innerHTML = `<p style="color:var(--text-muted); text-align:center; padding:20px 0;">Belum ada item</p>`;
  } else {
    container.innerHTML = items.map(([pid, item]) => `
      <div class="cart-row">
        <div>
          <div>${escapeHtml(item.produk.nama_produk)}</div>
          <div style="font-size:12px; color:var(--text-muted);">${rupiah(item.produk.harga)} x ${item.qty}</div>
        </div>
        <div class="qty-ctrl">
          <button onclick="changeQty(${pid}, -1)">-</button>
          <span>${item.qty}</span>
          <button onclick="changeQty(${pid}, 1)">+</button>
        </div>
      </div>
    `).join("");
  }

  const total = calcTotal();
  document.getElementById("cartTotal").textContent = rupiah(total);
  document.getElementById("btnCheckout").disabled = items.length === 0;
}

// ================= CHECKOUT MODAL =================
document.getElementById("btnCheckout").addEventListener("click", () => {
  document.getElementById("modalTotal").value = rupiah(calcTotal());
  document.getElementById("modalBayar").value = "";
  document.getElementById("modalKembalian").value = rupiah(0);
  document.getElementById("checkoutError").style.display = "none";
  document.getElementById("checkoutModal").style.display = "flex";
});

function closeCheckoutModal() {
  document.getElementById("checkoutModal").style.display = "none";
}

document.getElementById("modalBayar").addEventListener("input", (e) => {
  const bayar = parseFloat(e.target.value || 0);
  const kembalian = bayar - calcTotal();
  document.getElementById("modalKembalian").value = rupiah(Math.max(kembalian, 0));
});

document.getElementById("btnConfirmPay").addEventListener("click", async () => {
  const bayar = parseFloat(document.getElementById("modalBayar").value || 0);
  const total = calcTotal();
  const errBox = document.getElementById("checkoutError");

  if (bayar < total) {
    errBox.textContent = "Uang dibayar kurang dari total tagihan";
    errBox.style.display = "block";
    return;
  }

  const cartPayload = Object.entries(cart).map(([pid, item]) => ({
    product_id: parseInt(pid),
    qty: item.qty,
  }));

  const res = await fetch("/api/checkout", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      cart: cartPayload,
      payment: bayar,
      metode: document.getElementById("metodeBayar").value,
    }),
  });

  const data = await res.json();

  if (!res.ok) {
    errBox.textContent = data.error || "Gagal memproses transaksi";
    errBox.style.display = "block";
    return;
  }

  closeCheckoutModal();
  showReceipt(data);
  cart = {};
  renderCart();
  loadProducts(document.getElementById("searchInput").value);
});

// ================= RECEIPT MODAL =================
function showReceipt(trx) {
  const itemsHtml = trx.items.map(i => `
    <div class="receipt-line">
      <span>${escapeHtml(i.nama)} x${i.qty}</span>
      <span>${rupiah(i.subtotal)}</span>
    </div>
  `).join("");

  document.getElementById("receiptItems").innerHTML = itemsHtml;
  document.getElementById("rTotal").textContent = rupiah(trx.total);
  document.getElementById("rBayar").textContent = rupiah(trx.bayar);
  document.getElementById("rKembali").textContent = rupiah(trx.kembalian);
  document.getElementById("receiptModal").style.display = "flex";
}

function closeReceiptModal() {
  document.getElementById("receiptModal").style.display = "none";
}

// ================= SEARCH =================
let searchTimeout;
document.getElementById("searchInput").addEventListener("input", (e) => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => loadProducts(e.target.value), 250);
});

loadProducts();