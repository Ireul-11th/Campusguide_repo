/* Trang Quản lý tài khoản (chỉ quản trị viên) */
const U = { list: [], q: "", editId: null, loaded: false, failed: "" };
const me = CG.user;

async function load() {
  try { U.list = await api("/api/admin/users?q=" + encodeURIComponent(U.q)); U.loaded = true; U.failed = ""; }
  catch (e) { U.failed = e.message; }
  render();
}

function stats() {
  const all = U.q ? null : U.list;     // thống kê chỉ đúng khi chưa lọc
  if (!all) return;
  const n = (f) => all.filter(f).length;
  const card = (ic, tone, v, l) => `<div class="stat"><span class="ico ${tone}">${ic}</span><div><b>${v}</b><span>${l}</span></div></div>`;
  $("#uStats").innerHTML = card(ic("users"), "tone-a", all.length, "Tài khoản") + card(ic("shield-check"), "tone-b", n(u => u.role === "admin"), "Quản trị viên")
    + card(ic("database-zap"), "tone-c", n(u => u.role !== "admin" && u.can_manage_data), "Người dùng có quyền quản trị dữ liệu") + card(ic("circle-slash"), "tone-d", n(u => !u.is_active), "Đang bị khóa");
}

function roleBadge(u) { return u.role === "admin" ? `<span class="badge info">Quản trị viên</span>` : `<span class="badge mute">Người dùng</span>`; }
function actBadge(u) { return u.is_active ? `<span class="badge ok">Hoạt động</span>` : `<span class="badge err">Đã khóa</span>`; }
function cmdCell(u) {
  if (u.role === "admin") return `<span class="muted" style="font-size:13px">Mặc định</span>`;
  return `<label class="sw"><input type="checkbox" data-act="cmd" data-id="${u.id}" ${u.can_manage_data ? "checked" : ""} aria-label="Quyền quản trị dữ liệu của ${esc(u.username)}"><span></span></label>`;
}
function acts(u) {
  const self = u.id === me.id;
  return `<div class="row-acts"><button class="btn icon ghost" data-act="edit" data-id="${u.id}" aria-label="Sửa ${esc(u.username)}">${ic("pencil")}</button>
    <button class="btn icon ghost" data-act="del" data-id="${u.id}" aria-label="Xóa ${esc(u.username)}" ${self ? "disabled title=\"Không thể tự xóa\"" : ""}>${ic("trash")}</button></div>`;
}
const who = u => `<b>${esc(u.full_name || u.username)}</b>${u.id === me.id ? ` <span class="badge mute">Bạn</span>` : ""}<br><small class="muted">@${esc(u.username)}</small>`;

function render() {
  stats();
  const st = $("#uState");
  if (U.failed) { st.innerHTML = `<div class="notice-card bad" role="alert"><div class="row"><div style="flex:1"><h3 style="color:var(--danger)">Không tải được danh sách tài khoản</h3><p>${esc(U.failed)}</p><div class="btns"><button class="btn lg" data-act="reload">${ic("rotate-ccw")}Thử lại</button></div></div></div></div>`; return; }
  if (!U.loaded) { st.innerHTML = `<div class="skel" style="height:40px"></div>`; return; }
  if (!U.list.length) { st.innerHTML = `<div class="empty-state"><span class="ico">${ic("users", "lg")}</span><h3>Không có tài khoản phù hợp</h3><p>Thử từ khóa khác.</p></div>`; return; }
  st.innerHTML = `<table class="tbl only-md"><caption class="sr-only">Danh sách tài khoản</caption>
    <thead><tr><th scope="col">Tài khoản</th><th scope="col">Vai trò</th><th scope="col">Quản trị dữ liệu</th><th scope="col">Trạng thái</th><th scope="col">Đăng nhập gần nhất</th><th scope="col" class="r">Hội thoại</th><th scope="col"><span class="sr-only">Thao tác</span></th></tr></thead>
    <tbody>${U.list.map(u => `<tr><td>${who(u)}</td><td>${roleBadge(u)}</td><td>${cmdCell(u)}</td><td>${actBadge(u)}</td>
      <td class="muted" style="font-size:13px">${esc(fmtDateTime(u.last_login) || "Chưa đăng nhập")}</td><td class="r tnum muted">${u.n_conversations}</td><td>${acts(u)}</td></tr>`).join("")}</tbody></table>
    <ul class="jlist only-sm">${U.list.map(u => `<li class="jcard"><div style="display:flex;justify-content:space-between;gap:8px"><div>${who(u)}</div><div style="display:flex;gap:4px;flex-wrap:wrap;justify-content:flex-end">${roleBadge(u)}${actBadge(u)}</div></div>
      <div class="ft"><span>${u.role === "admin" ? "Quản trị dữ liệu: mặc định" : "Quản trị dữ liệu:"}</span>${u.role === "admin" ? "" : cmdCell(u)}${acts(u)}</div></li>`).join("")}</ul>`;
}

/* ---------- Thêm / sửa ---------- */
function openDlg(u) {
  U.editId = u ? u.id : null;
  $("#uTitle").textContent = u ? `Sửa tài khoản @${u.username}` : "Thêm tài khoản";
  $("#f_user").value = u ? u.username : ""; $("#f_user").disabled = !!u;
  $("#f_name").value = u ? u.full_name : "";
  $("#f_pw").value = ""; $("#f_pw_l").innerHTML = u ? "Mật khẩu mới" : `Mật khẩu <span class="req">*</span>`;
  $("#f_pw_h").textContent = u ? "Để trống nếu không đổi. Đổi mật khẩu sẽ đăng xuất tài khoản đó khỏi mọi thiết bị." : "Tối thiểu 8 ký tự, gồm cả chữ và số.";
  $("#f_role").value = u ? u.role : "user"; $("#f_cmd").checked = u ? u.can_manage_data : false; $("#f_active").checked = u ? u.is_active : true;
  const self = u && u.id === me.id;
  $("#f_role").disabled = self; $("#f_active").disabled = self;
  syncRole(); $("#uErr").hidden = true; $("#uDlg").showModal(); (u ? $("#f_name") : $("#f_user")).focus();
}
function syncRole() { const a = $("#f_role").value === "admin"; if (a) $("#f_cmd").checked = true; $("#f_cmd").disabled = a; }
$("#f_role").addEventListener("change", syncRole);
$("#uNew").addEventListener("click", () => openDlg(null));
$("#uCancel").addEventListener("click", () => $("#uDlg").close());

$("#uForm").addEventListener("submit", async e => {
  e.preventDefault();
  const err = $("#uErr"); err.hidden = true; $("#uSave").disabled = true;
  try {
    if (U.editId) {
      const body = { full_name: $("#f_name").value, role: $("#f_role").value, can_manage_data: $("#f_cmd").checked, is_active: $("#f_active").checked };
      if ($("#f_pw").value) body.password = $("#f_pw").value;
      await api("/api/admin/users/" + U.editId, { method: "PATCH", body });
      toast("Đã lưu thay đổi.", "ok");
    } else {
      await api("/api/admin/users", { method: "POST", body: { username: $("#f_user").value, full_name: $("#f_name").value, password: $("#f_pw").value,
        role: $("#f_role").value, can_manage_data: $("#f_cmd").checked, is_active: $("#f_active").checked } });
      toast("Đã thêm tài khoản.", "ok");
    }
    $("#uDlg").close(); load();
  } catch (ex) { err.textContent = ex.message; err.hidden = false; }
  finally { $("#uSave").disabled = false; }
});

/* ---------- Bảng ---------- */
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-act]"); if (!b || b.type === "checkbox") return;
  const u = U.list.find(x => x.id === +b.dataset.id);
  if (b.dataset.act === "reload") load();
  if (b.dataset.act === "edit" && u) openDlg(u);
  if (b.dataset.act === "del" && u) {
    if (!await confirmBox("Xóa tài khoản?", `Tài khoản @${u.username} và toàn bộ ${u.n_conversations} hội thoại của người này sẽ bị xóa vĩnh viễn.`, "Xóa")) return;
    try { await api("/api/admin/users/" + u.id, { method: "DELETE" }); toast("Đã xóa tài khoản.", "ok"); load(); }
    catch (ex) { toast(ex.message, "err"); }
  }
});
document.addEventListener("change", async e => {
  const c = e.target.closest('input[data-act="cmd"]'); if (!c) return;
  try {
    await api("/api/admin/users/" + c.dataset.id, { method: "PATCH", body: { can_manage_data: c.checked } });
    toast(c.checked ? "Đã cấp quyền Quản trị dữ liệu." : "Đã thu hồi quyền Quản trị dữ liệu.", "ok"); load();
  } catch (ex) { c.checked = !c.checked; toast(ex.message, "err"); }
});

let timer; $("#uSearch").addEventListener("input", e => { clearTimeout(timer); timer = setTimeout(() => { U.q = e.target.value.trim(); load(); }, 250); });
render(); load();
