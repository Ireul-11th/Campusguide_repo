/* Trang Thư viện văn bản */
const L = { docs: [], all: [], type: "", sort: "moi", loaded: false };
const f = { search: $("#fSearch"), year: $("#fYear"), valid: $("#fValid"), sort: $("#fSort") };
const normv = s => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/đ/g, "d").toLowerCase();

function skeleton() {
  return `<ul class="cards" aria-busy="true" aria-label="Đang tải">${Array.from({ length: 6 }, () => `<li class="card" style="padding:16px">
    <div class="skel" style="height:12px;width:96px"></div><div class="skel" style="height:16px;width:92%;margin-top:12px"></div>
    <div class="skel" style="height:16px;width:66%;margin-top:8px"></div><div class="skel" style="height:12px;width:100%;margin-top:16px"></div></li>`).join("")}</ul>`;
}

async function load() {
  $("#libBody").innerHTML = skeleton();
  $("#ketqua").textContent = "Đang tải danh sách văn bản…";
  try {
    const q = f.search.value.trim();
    L.docs = await api("/api/documents" + (q ? `?q=${encodeURIComponent(q)}` : ""));
    if (!q && !L.loaded) L.all = L.docs;
    L.loaded = true;
    fillFilters();
    render();
  } catch (e) {
    $("#ketqua").textContent = "Danh sách văn bản";
    $("#libBody").innerHTML = `<div class="error-state" role="alert"><span class="ico">${ic("triangle-alert", "lg")}</span>
      <div><b>Không tải được thư viện văn bản</b><p>${esc(e.message)}</p></div>
      <button class="btn lg" id="retry">${ic("rotate-ccw")}Thử lại</button></div>`;
    $("#retry").addEventListener("click", load);
  }
}

function fillFilters() {
  const base = L.all.length ? L.all : L.docs;
  const cur = f.year.value;
  const years = [...new Set(base.map(d => (d.issued_date || "").slice(0, 4)).filter(Boolean))].sort().reverse();
  f.year.innerHTML = `<option value="">Tất cả các năm</option>` + years.map(y => `<option>${y}</option>`).join("");
  if (years.includes(cur)) f.year.value = cur;

  const counts = {};
  L.docs.forEach(d => counts[d.doc_type] = (counts[d.doc_type] || 0) + 1);
  const opts = [["", "Tất cả", L.docs.length], ...Object.entries(CG.docTypes).map(([k, v]) => [k, v, counts[k] || 0])];
  $("#fTypes").innerHTML = opts.map(([k, v, c]) => `<label class="${L.type === k ? "on" : ""}">
    <input type="radio" name="loai" value="${k}" class="sr-only" ${L.type === k ? "checked" : ""}><span>${esc(v)}</span><span class="c tnum">${c}</span></label>`).join("");
}

function filtered() {
  return L.docs.filter(d =>
    (!L.type || d.doc_type === L.type) &&
    (!f.year.value || (d.issued_date || "").startsWith(f.year.value)) &&
    (!f.valid.value || d.validity === f.valid.value));
}

function sorted(rows) {
  const dateKey = d => d.issued_date || "";
  return [...rows].sort((a, b) => {
    if (L.sort === "ten") return a.title.localeCompare(b.title, "vi");
    const x = dateKey(a), y = dateKey(b);
    if (!x && y) return 1;           // chưa có ngày luôn xếp cuối
    if (x && !y) return -1;
    return L.sort === "cu" ? x.localeCompare(y) : y.localeCompare(x);
  });
}

function hasFilter() { return !!(f.search.value.trim() || L.type || f.year.value || f.valid.value); }

function render() {
  const rows = sorted(filtered());
  const active = hasFilter();
  $("#fClear").hidden = !active;
  $("#ketqua").innerHTML = `<strong class="tnum" style="color:var(--fg)">${rows.length}</strong> văn bản${active ? " phù hợp" : ""}`;
  const body = $("#libBody");
  if (!L.docs.length) {
    body.innerHTML = active
      ? `<div class="empty-state"><span class="ico">${ic("filter-x", "lg")}</span><h3>Không có văn bản phù hợp</h3><p>Thử bỏ bớt bộ lọc hoặc dùng từ khóa khác.</p><div class="act"><button class="btn lg" id="emptyClear">Xóa bộ lọc</button></div></div>`
      : `<div class="empty-state"><span class="ico">${ic("library", "lg")}</span><h3>Thư viện chưa có văn bản nào</h3><p>Khi quản trị viên tải lên và lập chỉ mục văn bản, chúng sẽ xuất hiện tại đây và được dùng làm căn cứ trả lời.</p><div class="act"><a class="btn lg" href="/admin">Đến trang Quản trị dữ liệu</a></div></div>`;
  } else if (!rows.length) {
    body.innerHTML = `<div class="empty-state"><span class="ico">${ic("filter-x", "lg")}</span><h3>Không có văn bản phù hợp</h3><p>Thử bỏ bớt bộ lọc hoặc dùng từ khóa khác.</p><div class="act"><button class="btn lg" id="emptyClear">Xóa bộ lọc</button></div></div>`;
  } else {
    body.innerHTML = `<ul class="cards">${rows.map((d, i) => {
      const old = d.validity === "het_hieu_luc" || d.validity === "da_thay_the";
      const sub = d.notes || d.replaced_by || d.issuer || "";
      return `<li><a class="dcard ${old ? "old" : ""}" href="/library/${d.id}" style="animation-delay:${Math.min(i, 8) * 40}ms">
        <div class="top"><span class="ty">${esc(d.doc_type_label)}</span>${validityBadge(d.validity, d.validity_label)}</div>
        <h3>${esc(d.title)}</h3>${sub ? `<p>${esc(d.notes ? d.notes : d.replaced_by ? "Thay thế: " + d.replaced_by : d.issuer)}</p>` : ""}
        <div class="meta"><span style="font-weight:500;color:oklch(.24 .035 262/.8)">${ic("file-text", "sm")}${esc(d.number) || "Chưa có số hiệu"}</span>
          <span>${ic("calendar", "sm")}${fmtDate(d.issued_date) || "Chưa có ngày"}</span>
          <span>${ic("file-stack", "sm")}${d.pages ? d.pages + " trang" : d.n_chunks + " đoạn"}</span>
          <span class="a">${ic("arrow-right")}</span></div></a></li>`;
    }).join("")}</ul>`;
  }
  $("#emptyClear")?.addEventListener("click", clearAll);
}

function clearAll() {
  const had = f.search.value.trim();
  f.search.value = f.year.value = f.valid.value = ""; L.type = "";
  had ? load() : (fillFilters(), render());
}

let t;
f.search.addEventListener("input", () => { clearTimeout(t); t = setTimeout(load, 350); });
f.year.addEventListener("change", render);
f.valid.addEventListener("change", render);
f.sort.addEventListener("change", () => { L.sort = f.sort.value; render(); });
$("#fTypes").addEventListener("change", e => { L.type = e.target.value; fillFilters(); render(); $("#fTypes input:checked")?.focus(); });
$("#fClear").addEventListener("click", clearAll);
load();
