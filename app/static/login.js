/* Trang đăng nhập / đăng ký */
const NEXT = (window.NEXT && window.NEXT.startsWith("/") && !window.NEXT.startsWith("//")) ? window.NEXT : "/";

function tab(reg) {
  $("#loginForm").hidden = reg; $("#regForm").hidden = !reg;
  $("#tabLogin").classList.toggle("on", !reg); $("#tabReg").classList.toggle("on", reg);
  $("#tabLogin").setAttribute("aria-selected", String(!reg)); $("#tabReg").setAttribute("aria-selected", String(reg));
  $("#authTitle").textContent = reg ? "Tạo tài khoản mới" : "Đăng nhập để tra cứu quy chế";
  (reg ? $("#r_name") : $("#l_user")).focus();
}
$("#tabLogin").addEventListener("click", () => tab(false));
$("#tabReg").addEventListener("click", () => tab(true));

async function submit(form, btn, errEl, path, body) {
  errEl.hidden = true; btn.disabled = true;
  try { await api(path, { method: "POST", body, noRedirect: true }); location.href = NEXT; }
  catch (e) { errEl.textContent = e.message; errEl.hidden = false; btn.disabled = false; }
}

$("#loginForm").addEventListener("submit", e => {
  e.preventDefault();
  const u = $("#l_user").value.trim(), p = $("#l_pw").value;
  if (!u || !p) { $("#loginErr").textContent = "Hãy nhập tên đăng nhập và mật khẩu."; $("#loginErr").hidden = false; return; }
  submit(e.target, $("#loginBtn"), $("#loginErr"), "/api/auth/login", { username: u, password: p });
});

$("#regForm").addEventListener("submit", e => {
  e.preventDefault();
  const err = $("#regErr"), u = $("#r_user").value.trim().toLowerCase(), p = $("#r_pw").value;
  const bad = m => { err.textContent = m; err.hidden = false; };
  if (!/^[a-z0-9_.]{3,32}$/.test(u)) return bad("Tên đăng nhập gồm 3–32 ký tự: chữ thường không dấu, số, dấu chấm hoặc gạch dưới.");
  if (p.length < 8 || /^\d+$/.test(p) || /^[A-Za-zÀ-ỹ]+$/.test(p)) return bad("Mật khẩu tối thiểu 8 ký tự, gồm cả chữ và số.");
  if (p !== $("#r_pw2").value) return bad("Hai mật khẩu chưa trùng nhau.");
  submit(e.target, $("#regBtn"), err, "/api/auth/register", { username: u, full_name: $("#r_name").value.trim(), password: p });
});
$("#l_user").focus();
