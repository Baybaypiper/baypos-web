let kategoriList = [];

function rupiah(n) {
  return "Rp" + Math.round(n).toLocaleString("id-ID");
}

function escapeHtml(s) {
  const div = document.createElement("div");
  div.textContent = s || "";
  return div.innerHTML;
}

async function loadKategori() {
  const res = await fetch("/api/produk/kategori");
  kategoriList = await res.json();
  const sel = document.getElementById("fKategori");
  sel.innerHTML = `<option value="">-- Tanpa kategori --</option>` +
    kategoriList.map(k => `<option value="${k.id}">${escapeHtml(k.parent)} - ${escapeHtml(k.nama)}</option>`).join("");
}

async function loadProduk(keyword = "") {
  const url = keyword ? `/api/produk?q=${encodeURIComponent(keyword)}` : "/api/produk";
  const res = await fetch(url);
  const data = await res.json();
  renderTable(data);
}

function renderTable(data) {
  const tbody = document.getElementById("produkTable");

  if (data.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" style="text-align:center; color:var(--text-muted);">Belum ada produk</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(p => {
    const isLow = p.stok <= p.stok_minim;
    return `
      <tr>
        <td>${escapeHtml(p.nama_produk)}</td>
        <td>${escapeHtml(p.kategori_nama || "-")}</td>
        <td>${rupiah(p.harga)}</td>
        <td>${rupiah(p.harga_modal || 0)}</td>
        <td>${p.stok} ${escapeHtml(p.satuan || "")}</td>
        <td>${isLow ? '<span class="badge low">Stok Minim</span>' : '<span class="badge ok">Aman</span>'}</td>
        <td style="white-space:nowrap;">
          <button class="btn secondary" style="padding:6px 10px; font-size:12px;" onclick='editProduk(${JSON.stringify(p)})'>Edit</button>
          <button class="btn danger" style="padding:6px 10px; font-size:12px;" onclick="deleteProduk(${p.id}, '${escapeHtml(p.nama_produk)}')">Hapus</button>
        </td>
      </tr>
    `;
  }).join("");
}

function openProdukModal() {
  document.getElementById("modalTitle").textContent = "Produk Baru";
  document.getElementById("fId").value = "";
  document.getElementById("fNama").value = "";
  document.getElementById("fKategori").value = "";
  document.getElementById("fHarga").value = "";
  document.getElementById("fHargaModal").value = "";
  document.getElementById("fStok").value = "0";
  document.getElementById("fStokMinim").value = "5";
  document.getElementById("fSatuan").value = "pcs";
  document.getElementById("produkError").style.display = "none";
  document.getElementById("produkModal").style.display = "flex";
}

function editProduk(p) {
  document.getElementById("modalTitle").textContent = "Edit Produk";
  document.getElementById("fId").value = p.id;
  document.getElementById("fNama").value = p.nama_produk;
  document.getElementById("fKategori").value = p.kategori_id || "";
  document.getElementById("fHarga").value = p.harga;
  document.getElementById("fHargaModal").value = p.harga_modal || 0;
  document.getElementById("fStok").value = p.stok;
  document.getElementById("fStokMinim").value = p.stok_minim;
  document.getElementById("fSatuan").value = p.satuan || "pcs";
  document.getElementById("produkError").style.display = "none";
  document.getElementById("produkModal").style.display = "flex";
}

function closeProdukModal() {
  document.getElementById("produkModal").style.display = "none";
}

async function saveProduk() {
  const id = document.getElementById("fId").value;
  const payload = {
    nama_produk: document.getElementById("fNama").value.trim(),
    kategori_id: document.getElementById("fKategori").value || null,
    harga: parseFloat(document.getElementById("fHarga").value || 0),
    harga_modal: parseFloat(document.getElementById("fHargaModal").value || 0),
    stok: parseFloat(document.getElementById("fStok").value || 0),
    stok_minim: parseFloat(document.getElementById("fStokMinim").value || 5),
    satuan: document.getElementById("fSatuan").value.trim() || "pcs",
  };

  const errBox = document.getElementById("produkError");

  if (!payload.nama_produk) {
    errBox.textContent = "Nama produk wajib diisi";
    errBox.style.display = "block";
    return;
  }

  const url = id ? `/api/produk/${id}` : "/api/produk";
  const method = id ? "PUT" : "POST";

  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await res.json();

  if (!res.ok) {
    errBox.textContent = data.error || "Gagal menyimpan produk";
    errBox.style.display = "block";
    return;
  }

  closeProdukModal();
  loadProduk(document.getElementById("searchInput").value);
}

async function deleteProduk(id, nama) {
  if (!confirm(`Hapus produk "${nama}"? Tindakan ini tidak bisa dibatalkan.`)) return;

  await fetch(`/api/produk/${id}`, { method: "DELETE" });
  loadProduk(document.getElementById("searchInput").value);
}

let searchTimeout;
document.getElementById("searchInput").addEventListener("input", (e) => {
  clearTimeout(searchTimeout);
  searchTimeout = setTimeout(() => loadProduk(e.target.value), 250);
});

loadKategori();
loadProduk();