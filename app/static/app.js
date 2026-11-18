/* Tiện ích dùng chung cho mọi trang */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function api(path, { method = "GET", body, form, noRedirect = false } = {}) {
  const headers = { "X-Requested-With": "cg" };
  let payload;
  if (form) payload = form;
  else if (body !== undefined) { headers["Content-Type"] = "application/json"; payload = JSON.stringify(body); }
  let res;
  try { res = await fetch(path, { method, headers, body: payload }); }
  catch { throw new ApiError("Không kết nối được tới máy chủ. Hãy kiểm tra mạng hoặc xem máy chủ còn chạy không.", 0); }
  if (res.status === 401 && !noRedirect && !location.pathname.startsWith("/login")) {
    location.href = "/login?next=" + encodeURIComponent(location.pathname + location.search);
    return new Promise(() => {});
  }
  if (!res.ok) {
    let msg = `Máy chủ trả về lỗi ${res.status}.`;
    try {
      const j = await res.json();
      if (typeof j.detail === "string") msg = j.detail;
      else if (Array.isArray(j.detail)) msg = "Dữ liệu chưa hợp lệ: " + j.detail.map(d => d.msg).join("; ");
    } catch {}
    throw new ApiError(msg, res.status);
  }
  return res.status === 204 ? null : res.json();
}

function toast(msg, kind = "") {
  const t = document.createElement("div");
  t.className = "toast " + kind;
  t.textContent = msg;
  $("#toasts").appendChild(t);
  setTimeout(() => t.remove(), 4000);
}

function confirmBox(title, msg, okLabel = "Đồng ý") {
  return new Promise(resolve => {
    const d = $("#confirmDlg");
    $("#confirmTitle").textContent = title;
    $("#confirmMsg").textContent = msg;
    $("#confirmOk").textContent = okLabel;
    d.addEventListener("close", () => resolve(d.returnValue === "ok"), { once: true });
    d.returnValue = "cancel";
    d.showModal();
  });
}

function fmtDate(s) {
  if (!s) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : s;
}
function fmtDateTime(s) {
  if (!s) return "";
  const d = new Date(s.replace(" ", "T") + "Z");
  if (isNaN(d)) return s;
  return d.toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

function validityBadge(key, label) {
  const cls = { dang_hieu_luc: "ok", mot_phan: "warn", het_hieu_luc: "mute", da_thay_the: "warn", chua_xac_minh: "mute" }[key] || "mute";
  const icon = { dang_hieu_luc: "circle-check", mot_phan: "circle-dashed", het_hieu_luc: "circle-slash", da_thay_the: "circle-dashed", chua_xac_minh: "circle-dashed" }[key] || "circle-dashed";
  return `<span class="badge ${cls}">${ic(icon, "sm")}${esc(label)}</span>`;
}


/* Biểu tượng (kiểu Lucide), dùng ic("tên") trong JS hoặc <i data-i="tên"></i> trong HTML */
const ICONS = {
  "messages-square": '<path d="M16 10a2 2 0 0 1-2 2H6.8L3 15.5V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2Z"/><path d="M20 9a2 2 0 0 1 2 2v10.5L18.2 18H11a2 2 0 0 1-2-2v-1"/>',
  "library": '<path d="m16 6 4 14M12 6v14M8 8v12M4 4v16"/>',
  "database-zap": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.7 4 3 9 3M21 5v4M3 12c0 1.7 4 3 9 3M21 15l-3 4h4l-3 4"/>',
  "history": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5M12 7v5l4 2"/>',
  "plus": '<path d="M12 5v14M5 12h14"/>',
  "search": '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  "arrow-up": '<path d="m5 12 7-7 7 7M12 19V5"/>',
  "arrow-up-right": '<path d="M7 17 17 7M7 7h10v10"/>',
  "arrow-right": '<path d="M5 12h14m-7-7 7 7-7 7"/>',
  "arrow-left": '<path d="m12 19-7-7 7-7M19 12H5"/>',
  "check": '<path d="M20 6 9 17l-5-5"/>',
  "x": '<path d="M18 6 6 18M6 6l12 12"/>',
  "copy": '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  "thumbs-up": '<path d="M7 10v12M15 5.9 14 10h5.8a2 2 0 0 1 1.9 2.5l-2.3 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.8a2 2 0 0 0 1.8-1.1L12 2a3.1 3.1 0 0 1 3 3.9Z"/>',
  "thumbs-down": '<path d="M17 14V2M9 18.1 10 14H4.2a2 2 0 0 1-1.9-2.5l2.3-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.8a2 2 0 0 0-1.8 1.1L12 22a3.1 3.1 0 0 1-3-3.9Z"/>',
  "shield-check": '<path d="M20 13c0 5-3.5 7.5-7.7 8.9a1 1 0 0 1-.6 0C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.2-2.7a1.2 1.2 0 0 1 1.6 0C14.5 3.8 17 5 19 5a1 1 0 0 1 1 1Z"/><path d="m9 12 2 2 4-4"/>',
  "book-open-check": '<path d="M12 21V7M16 12l2 2 4-4M22 6V4a1 1 0 0 0-1-1h-5a4 4 0 0 0-4 4 4 4 0 0 0-4-4H3a1 1 0 0 0-1 1v13a1 1 0 0 0 1 1h6a3 3 0 0 1 3 3 3 3 0 0 1 3-3h6a1 1 0 0 0 1-1v-1.3"/>',
  "file-search": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6"/><circle cx="11.5" cy="14.5" r="2.5"/><path d="m13.3 16.3 1.7 1.7"/>',
  "file-text": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>',
  "file-up": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M12 12v6M9 15l3-3 3 3"/>',
  "file-stack": '<path d="M21 7h-3a2 2 0 0 1-2-2V2"/><path d="M21 6v6.5c0 .8-.7 1.5-1.5 1.5h-7c-.8 0-1.5-.7-1.5-1.5v-9c0-.8.7-1.5 1.5-1.5H17Z"/><path d="M7 8v8.8c0 .3.2.6.4.8.2.2.5.4.8.4H15M3 12v8.8c0 .3.2.6.4.8.2.2.5.4.8.4H11"/>',
  "corner-down-right": '<path d="m15 10 5 5-5 5"/><path d="M4 4v7a4 4 0 0 0 4 4h12"/>',
  "search-x": '<path d="m13.5 8.5-5 5M8.5 8.5l5 5"/><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
  "triangle-alert": '<path d="m21.7 18-8-14a2 2 0 0 0-3.5 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3Z"/><path d="M12 9v4M12 17h.01"/>',
  "rotate-ccw": '<path d="M3 12a9 9 0 1 0 9-9 9.8 9.8 0 0 0-6.7 2.7L3 8"/><path d="M3 3v5h5"/>',
  "trash": '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M10 11v6M14 11v6"/>',
  "pencil": '<path d="M21.2 6.1a2.1 2.1 0 0 0-3-3L3.7 17.6a2 2 0 0 0-.5.9l-1.2 4.2a.5.5 0 0 0 .6.6l4.2-1.2a2 2 0 0 0 .9-.5Z"/><path d="m15 5 4 4"/>',
  "calendar": '<path d="M8 2v4M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/>',
  "calendar-clock": '<path d="M21 7.5V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3.5M16 2v4M8 2v4M3 10h5"/><circle cx="16" cy="16" r="6"/><path d="M16 14v2l1 1"/>',
  "filter-x": '<path d="M13.013 3H2l8 9.46V19l4 2v-8.54l.9-1.055M22 3l-5 5M17 3l5 5"/>',
  "chevron-left": '<path d="m15 18-6-6 6-6"/>',
  "chevron-right": '<path d="m9 18 6-6-6-6"/>',
  "external-link": '<path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>',
  "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/>',
  "gauge": '<path d="m12 14 4-4M3.3 19a10 10 0 1 1 17.4 0"/>',
  "loader": '<path d="M21 12a9 9 0 1 1-6.2-8.6"/>',
  "alert-circle": '<circle cx="12" cy="12" r="10"/><path d="M12 8v4M12 16h.01"/>',
  "circle-check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
  "circle-slash": '<circle cx="12" cy="12" r="10"/><path d="m9 15 6-6"/>',
  "circle-dashed": '<path d="M10.1 2.2a10 10 0 0 1 3.8 0M17.6 3.7a10 10 0 0 1 2.7 2.7M21.8 10.1a10 10 0 0 1 0 3.8M20.3 17.6a10 10 0 0 1-2.7 2.7M13.9 21.8a10 10 0 0 1-3.8 0M6.4 20.3a10 10 0 0 1-2.7-2.7M2.2 13.9a10 10 0 0 1 0-3.8M3.7 6.4a10 10 0 0 1 2.7-2.7"/>',
  "inbox": '<path d="M22 12h-6l-2 3h-4l-2-3H2"/><path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1Z"/>',
  "database": '<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5M3 12a9 3 0 0 0 18 0"/>',
  "quote": '<path d="M16 3a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2 1 1 0 0 1 1 1v1a2 2 0 0 1-2 2 1 1 0 0 0-1 1v2a1 1 0 0 0 1 1 6 6 0 0 0 6-6V5a2 2 0 0 0-2-2ZM5 3a2 2 0 0 0-2 2v6a2 2 0 0 0 2 2 1 1 0 0 1 1 1v1a2 2 0 0 1-2 2 1 1 0 0 0-1 1v2a1 1 0 0 0 1 1 6 6 0 0 0 6-6V5a2 2 0 0 0-2-2Z"/>',
  "badge-check": '<path d="M3.9 8.7a4 4 0 0 1 2.4-2.4 4 4 0 0 1 5.7-2 4 4 0 0 1 5.7 2 4 4 0 0 1 2.4 2.4 4 4 0 0 1 0 6.6 4 4 0 0 1-2.4 2.4 4 4 0 0 1-5.7 2 4 4 0 0 1-5.7-2A4 4 0 0 1 3.9 15.3a4 4 0 0 1 0-6.6Z"/><path d="m9 12 2 2 4-4"/>',
  "award": '<circle cx="12" cy="8" r="6"/><path d="M15.5 12.9 17 22l-5-3-5 3 1.5-9.1"/>',
  "wallet": '<path d="M19 7V4a1 1 0 0 0-1-1H5a2 2 0 0 0 0 4h15a1 1 0 0 1 1 1v4h-3a2 2 0 0 0 0 4h3a1 1 0 0 0 1-1v-2a1 1 0 0 0-1-1"/><path d="M3 5v14a2 2 0 0 0 2 2h15a1 1 0 0 0 1-1v-4"/>',
  "layers": '<path d="M12.8 2.2a2 2 0 0 0-1.6 0L2.6 6.1a1 1 0 0 0 0 1.8l8.6 3.9a2 2 0 0 0 1.6 0l8.6-3.9a1 1 0 0 0 0-1.8Z"/><path d="m22 17.7-9.2 4.2a2 2 0 0 1-1.6 0L2 17.7M22 12.7l-9.2 4.2a2 2 0 0 1-1.6 0L2 12.7"/>',
  "graduation-cap": '<path d="M21.4 10.9a1 1 0 0 0 0-1.8L12.8 5.2a2 2 0 0 0-1.6 0L2.6 9.1a1 1 0 0 0 0 1.8l8.6 3.9a2 2 0 0 0 1.6 0Z"/><path d="M22 10v6M6 12.5V16a6 3 0 0 0 12 0v-3.5"/>',
  "refresh": '<path d="M3 12a9 9 0 0 1 9-9 9.8 9.8 0 0 1 6.7 2.7L21 8M21 3v5h-5M21 12a9 9 0 0 1-9 9 9.8 9.8 0 0 1-6.7-2.7L3 16M8 16H3v5"/>',
  "file-question": '<path d="M12 17h.01M20 22a2 2 0 0 0 2-2V7l-5-5H6a2 2 0 0 0-2 2v3"/><path d="M14 2v4a2 2 0 0 0 2 2h4M4 18.5a2.5 2.5 0 0 1 5 0c0 1.5-2.5 2-2.5 3.5"/>',
  "users": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/>',
  "key-round": '<path d="M2.586 17.414A2 2 0 0 0 2 18.828V21a1 1 0 0 0 1 1h3a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h1a1 1 0 0 0 1-1v-1a1 1 0 0 1 1-1h.172a2 2 0 0 0 1.414-.586l.814-.814a6.5 6.5 0 1 0-4-4z"/><circle cx="16.5" cy="7.5" r=".5" fill="currentColor"/>',
  "log-out": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9"/>',
  "chevron-down": '<path d="m6 9 6 6 6-6"/>',
  "user-plus": '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
  "shield-check": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="m9 12 2 2 4-4"/>',
  "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
};
function ic(name, size = "") {
  return `<svg class="ic ${size}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;
}
function hydrateIcons(root = document) {
  $$("i[data-i]", root).forEach(e => { e.outerHTML = ic(e.dataset.i, e.dataset.s || ""); });
}
hydrateIcons();

/* Trạng thái hệ thống ở thanh trên */
(async () => {
  if (!CG.user) return;
  try {
    const h = await api("/api/health");
    window.CG.health = h;
    const parts = [];
    parts.push(h.index.docs ? `${h.index.docs} văn bản · ${h.index.chunks} đoạn` : "Chưa có tài liệu");
    parts.push(h.llm_configured ? `LLM: ${h.llm}` : "Chưa cấu hình LLM");
    $("#healthText").textContent = parts.join(" · ");
    $("#health").title = parts.join("\n");
    $("#healthDot").classList.add(h.llm_configured && h.index.docs ? "ok" : "warn");
    document.dispatchEvent(new CustomEvent("cg:health", { detail: h }));
  } catch {
    $("#healthText").textContent = "Không kết nối được máy chủ";
  }
})();


/* Menu tài khoản: đổi mật khẩu, đăng xuất */
(() => {
  const u = CG.user; if (!u) return;
  const btn = $("#userBtn"), menu = $("#userMenu"); if (!btn) return;
  const close = () => { menu.hidden = true; btn.setAttribute("aria-expanded", "false"); };
  btn.addEventListener("click", e => { e.stopPropagation(); menu.hidden = !menu.hidden; btn.setAttribute("aria-expanded", String(!menu.hidden)); });
  document.addEventListener("click", e => { if (!menu.contains(e.target)) close(); });
  document.addEventListener("keydown", e => { if (e.key === "Escape") close(); });
  $("#logoutBtn").addEventListener("click", async () => {
    try { await api("/api/auth/logout", { method: "POST", noRedirect: true }); } catch {}
    location.href = "/login";
  });
  const dlg = $("#pwDlg");
  $("#pwOpen").addEventListener("click", () => { close(); $("#pwForm").reset(); $("#pwErr").hidden = true; dlg.showModal(); });
  $("#pwCancel").addEventListener("click", () => dlg.close());
  $("#pwForm").addEventListener("submit", async e => {
    e.preventDefault();
    const err = $("#pwErr"); err.hidden = true;
    if ($("#pw_new").value !== $("#pw_new2").value) { err.textContent = "Hai mật khẩu mới chưa trùng nhau."; err.hidden = false; return; }
    try {
      await api("/api/auth/password", { method: "POST", body: { current: $("#pw_cur").value, new: $("#pw_new").value } });
      dlg.close(); toast("Đã đổi mật khẩu. Các thiết bị khác đã bị đăng xuất.", "ok");
    } catch (ex) { err.textContent = ex.message; err.hidden = false; }
  });
})();
