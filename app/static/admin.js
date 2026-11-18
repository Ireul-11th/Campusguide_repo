/* Trang Quản trị dữ liệu */
const A = { docs: [], timer: null, uploading: false, editId: null, replaceId: null, filter: "all", loaded: false, failedLoad: false };
const STEPS = [
  { key: "pending", label: "Chờ xử lý" },
  { key: "extracting", label: "Trích xuất" },
  { key: "chunking", label: "Chia đoạn" },
  { key: "indexing", label: "Lập chỉ mục" },
  { key: "done", label: "Hoàn tất" },
];
const RUNNING = ["pending", "extracting", "chunking", "indexing"];
const isRunning = d => RUNNING.includes(d.proc_status);

function unauthorized(e) {
  if (e.status === 403) { toast(e.message, "err"); setTimeout(() => location.reload(), 1200); return true; }
  return false;
}

/* ---------- Danh sách ---------- */
async function loadDocs(quiet = false) {
  if (!quiet) { A.failedLoad = false; renderAll(); }
  try {
    A.docs = await api("/api/admin/documents");
    A.loaded = true; A.failedLoad = false;
  } catch (e) {
    if (unauthorized(e)) return;
    if (!quiet) { A.failedLoad = e.message; }
  }
  renderAll();
  clearTimeout(A.timer);
  if (A.docs.some(isRunning)) A.timer = setTimeout(() => loadDocs(true), 1500);
}

function counts() {
  const c = { all: A.docs.length, processing: 0, done: 0, failed: 0, chunks: 0 };
  A.docs.forEach(d => {
    if (isRunning(d)) c.processing++;
    else if (d.proc_status === "done") { c.done++; c.chunks += d.n_chunks || 0; }
    else c.failed++;
  });
  return c;
}

function stepper(d) {
  const failed = d.proc_status === "failed", done = d.proc_status === "done";
  const idx = failed ? Math.max(0, STEPS.findIndex(s => s.key === (d.failed_stage || "extracting"))) : STEPS.findIndex(s => s.key === d.proc_status);
  const label = failed ? `Thất bại ở bước ${STEPS[idx].label}` : done ? "Hoàn tất" : `${d.proc_label} · bước ${idx + 1}/5`;
  return `<div style="min-width:0"><p class="sr-only">${esc(label)}</p>
    <ol class="stepper" aria-hidden="true">${STEPS.map((s, i) => {
      const st = failed && i === idx ? "failed" : (i < idx || done) ? "done" : i === idx ? "active" : "todo";
      const c = st === "done" ? ic("check", "sm") : st === "failed" ? ic("x", "sm") : i + 1;
      const last = i === STEPS.length - 1;
      return `<li title="${s.label}"><span class="c ${st}">${c}</span>${last ? "" :
        `<span class="ln ${i < idx || done ? "full" : ""} ${st === "active" ? "run" : ""}"><i></i></span>`}</li>`;
    }).join("")}</ol>
    <p class="stp-l ${failed ? "bad" : done ? "ok" : ""}">${esc(label)}</p></div>`;
}

function jobInfo(d) {
  const line = [d.number, d.doc_type_label, d.validity_label].filter(Boolean).join(" · ");
  const err = d.proc_status === "failed" && d.error ? `<p class="jerr" role="alert">${esc(d.error)}</p>` : "";
  const warn = d.proc_status === "done" && d.error ? `<p class="jwarn">${ic("triangle-alert", "sm")} <strong>Cảnh báo chất lượng:</strong> ${esc(d.error)}</p>` : "";
  return `<p class="jt">${esc(d.title)}</p><p class="js">${esc(line)} · ${fmtDateTime(d.created_at)}${d.updated_at && d.updated_at !== d.created_at ? ` · cập nhật ${fmtDateTime(d.updated_at)}` : ""}</p>
    <p class="jf">${esc(d.filename)}</p>${err}${warn}`;
}

function actions(d) {
  const b = isRunning(d);
  return `<div class="acts">
    <button class="btn sm" title="Sửa thông tin" data-act="edit" ${b ? "disabled" : ""}>${ic("pencil", "sm")}<span class="lb">Sửa</span></button>
    <button class="btn sm" title="Thay file" data-act="replace" ${b ? "disabled" : ""}>${ic("file-up", "sm")}<span class="lb">Thay file</span></button>
    <button class="btn sm" title="${d.proc_status === "done" ? "Lập lại chỉ mục" : "Thử lại"}" data-act="retry" ${b ? "disabled" : ""}>${ic("rotate-ccw", "sm")}<span class="lb">${d.proc_status === "done" ? "Lập lại" : "Thử lại"}</span></button>
    <button class="btn sm ghost" title="Xóa" data-act="del" ${b ? "disabled" : ""} aria-label="Xóa ${esc(d.title)}">${ic("trash", "sm")}</button></div>`;
}

function statCard(label, value, icon, tone) {
  return `<div class="stat"><span class="ico ${tone}">${ic(icon)}</span><div><b class="tnum">${value}</b><span>${label}</span></div></div>`;
}

function renderAll() {
  const c = counts();
  $("#stats").innerHTML = statCard("Văn bản trong hệ thống", c.all, "file-text", "tone-a") + statCard("Đang xử lý", c.processing, "loader", "tone-b")
    + statCard("Đoạn đã lập chỉ mục", c.chunks, "database", "tone-c") + statCard("Thất bại cần xử lý", c.failed, "alert-circle", "tone-d");
  $("#liveNote").innerHTML = c.processing
    ? `<span class="live"><i></i><i></i></span>Tự cập nhật khi đang xử lý`
    : `<span style="color:var(--success);display:inline-flex">${ic("circle-check", "sm")}</span>Không có tác vụ đang chạy`;
  const F = [["all", "Tất cả", c.all], ["processing", "Đang xử lý", c.processing], ["done", "Hoàn tất", c.done], ["failed", "Thất bại", c.failed]];
  $("#seg").innerHTML = F.map(([k, l, n]) => `<button role="tab" type="button" data-f="${k}" aria-selected="${A.filter === k}">${l}<span class="c tnum">${n}</span></button>`).join("");

  const st = $("#adminState");
  if (!A.loaded && !A.failedLoad) {
    st.innerHTML = `<ul class="jlist" aria-busy="true">${Array.from({ length: 3 }, () => `<li class="jcard"><div class="skel" style="height:14px;width:50%"></div><div class="skel" style="height:12px;width:33%;margin-top:8px"></div></li>`).join("")}</ul>`;
    return;
  }
  if (A.failedLoad) {
    st.innerHTML = `<div class="error-state" role="alert"><span class="ico">${ic("triangle-alert", "lg")}</span><div><b>Không tải được hàng đợi xử lý</b><p>${esc(A.failedLoad)}</p></div><button class="btn lg" id="retryLoad">${ic("rotate-ccw")}Thử lại</button></div>`;
    $("#retryLoad").addEventListener("click", () => loadDocs());
    return;
  }
  if (!A.docs.length) {
    st.innerHTML = `<div class="empty-state"><span class="ico">${ic("inbox", "lg")}</span><h3>Chưa có văn bản nào được tải lên</h3><p>Dùng biểu mẫu bên cạnh để tải tệp đầu tiên. Tiến trình xử lý sẽ hiển thị tại đây.</p></div>`;
    return;
  }
  const rows = A.docs.filter(d => A.filter === "all" || (A.filter === "processing" ? isRunning(d) : A.filter === "done" ? d.proc_status === "done" : d.proc_status === "failed"));
  if (!rows.length) {
    st.innerHTML = `<div class="empty-state"><span class="ico">${ic(A.filter === "failed" ? "circle-check" : "inbox", "lg")}</span><h3>${A.filter === "failed" ? "Không có tác vụ thất bại" : "Không có văn bản ở trạng thái này"}</h3><p>Chọn bộ lọc khác để xem các văn bản còn lại.</p><div class="act"><button class="btn lg" data-f="all">Xem tất cả</button></div></div>`;
    return;
  }
  st.innerHTML = `<table class="tbl only-md"><caption class="sr-only">Trạng thái xử lý văn bản</caption>
    <thead><tr><th scope="col">Văn bản</th><th scope="col" style="width:36%">Tiến trình</th><th scope="col" class="r">Đoạn</th><th scope="col"><span class="sr-only">Thao tác</span></th></tr></thead>
    <tbody>${rows.map(d => `<tr data-id="${d.id}"><td>${jobInfo(d)}</td><td>${stepper(d)}</td>
      <td class="r tnum muted">${d.n_chunks || "–"}</td><td>${actions(d)}</td></tr>`).join("")}</tbody></table>
    <ul class="jlist only-sm">${rows.map(d => `<li class="jcard" data-id="${d.id}">
      <div class="h"><div style="min-width:0">${jobInfo(d)}</div></div>
      <div style="margin-top:12px">${stepper(d)}</div>
      <div class="ft"><span>${d.n_chunks ? d.n_chunks + " đoạn" : ""}</span>${actions(d)}</div></li>`).join("")}</ul>`;
}

document.addEventListener("click", async e => {
  const fb = e.target.closest("[data-f]");
  if (fb && $("#adminBox").contains(fb)) { A.filter = fb.dataset.f; renderAll(); return; }
  const b = e.target.closest("[data-act]");
  const row = b?.closest("[data-id]");
  if (!b || !row || b.disabled || !$("#adminState").contains(b)) return;
  const id = +row.dataset.id, d = A.docs.find(x => x.id === id);
  if (!d) return;
  try {
    if (b.dataset.act === "retry") {
      if (d.proc_status === "done" && !await confirmBox("Lập lại chỉ mục?", `Tài liệu "${d.title}" sẽ được xử lý lại từ file gốc.`, "Lập lại")) return;
      await api(`/api/admin/documents/${id}/retry`, { method: "POST" }); loadDocs(true);
    }
    if (b.dataset.act === "del") {
      if (!await confirmBox("Xóa tài liệu?", `"${d.title}" sẽ bị xóa khỏi chỉ mục và thư viện, kể cả file gốc. Không thể hoàn tác.`, "Xóa")) return;
      await api(`/api/admin/documents/${id}`, { method: "DELETE" });
      toast("Đã xóa tài liệu", "ok"); loadDocs(true);
    }
    if (b.dataset.act === "edit") openEdit(d);
    if (b.dataset.act === "replace") { A.replaceId = id; $("#replaceInput").value = ""; $("#replaceInput").click(); }
  } catch (err) { if (!unauthorized(err)) toast(err.message, "err"); }
});

/* ---------- Tải lên ---------- */
const form = $("#uploadForm");
const maxMb = () => CG.health?.max_upload_mb || 25;
const allowedExt = () => CG.health?.allowed_ext || [".pdf", ".docx", ".txt", ".md"];
const fmtSize = b => b > 1048576 ? `${(b / 1048576).toFixed(1).replace(".", ",")} MB` : `${Math.max(1, Math.round(b / 1024))} KB`;
document.addEventListener("cg:health", () => {
  $("#fileHint").textContent = `Hỗ trợ ${allowedExt().map(x => x.slice(1).toUpperCase()).join(", ")}. Tối đa ${maxMb()} MB. PDF scan cần bật OCR.`;
});

const fileIn = $("#file"), drop = $("#dropZone"), chip = $("#fileChip");
function setFileErr(msg) { const p = $("#fileErr"); p.textContent = msg || ""; p.hidden = !msg; drop.classList.toggle("bad", !!msg); }
function setUploadErr(msg) { const p = $("#uploadErr"); p.textContent = msg || ""; p.hidden = !msg; }

function acceptFile(f) {
  if (!f) return;
  const ext = "." + f.name.split(".").pop().toLowerCase();
  if (!allowedExt().includes(ext)) return setFileErr(`Định dạng ${ext} không được hỗ trợ.`);
  if (f.size > maxMb() * 1048576) return setFileErr(`Tệp vượt quá ${maxMb()} MB.`);
  setFileErr("");
  const dt = new DataTransfer(); dt.items.add(f); fileIn.files = dt.files;
  $("#fcName").textContent = f.name; $("#fcSize").textContent = `${fmtSize(f.size)} · ${ext.slice(1).toUpperCase()}`;
  chip.hidden = false; drop.hidden = true;
  if (!$("#u_title").value) $("#u_title").value = f.name.replace(/\.[^.]+$/, "").replace(/[-_]+/g, " ");
  detectFields(f);
}

/* ---------- Tự điền thông tin từ nội dung file ---------- */
const AUTO_FIELDS = ["title", "doc_type", "number", "issuer", "issued_date", "effective_date", "replaced_by"];
const AUTO_LABEL = { title: "Tên văn bản", doc_type: "Loại văn bản", number: "Số hiệu", issuer: "Cơ quan ban hành", issued_date: "Ngày ban hành", effective_date: "Ngày hiệu lực", replaced_by: "Văn bản thay thế" };
const touched = new Set();
let detectSeq = 0;
AUTO_FIELDS.forEach(k => $("#u_" + k).addEventListener("input", e => { if (e.isTrusted) { touched.add(k); e.target.classList.remove("auto"); } }));

function clearAuto() { touched.clear(); AUTO_FIELDS.forEach(k => $("#u_" + k).classList.remove("auto")); $("#detectNote").hidden = true; }

async function detectFields(f) {
  const seq = ++detectSeq, note = $("#detectNote");
  note.hidden = false; note.className = "hint"; note.textContent = "Đang đọc nội dung file để gợi ý thông tin…";
  try {
    const fd = new FormData(); fd.append("file", f);
    const res = await api("/api/admin/documents/detect", { method: "POST", form: fd });
    if (seq !== detectSeq) return;
    const got = res.fields || {}, done = [];
    for (const k of AUTO_FIELDS) {
      if (!got[k] || touched.has(k)) continue;
      const el = $("#u_" + k);
      el.value = got[k]; el.classList.add("auto"); done.push(AUTO_LABEL[k]);
    }
    if (done.length) { note.className = "hint auto-note"; note.textContent = `Đã tự điền ${done.length} mục từ nội dung file (${done.join(", ")}). Hãy kiểm tra lại trước khi tải lên; Tình trạng hiệu lực cần bạn chọn.`; }
    else { note.className = "hint"; note.textContent = "Không nhận ra thông tin nào trong file, bạn hãy nhập tay."; }
  } catch (e) {
    if (seq === detectSeq) { note.className = "hint"; note.textContent = "Không đọc được file để gợi ý, bạn hãy nhập tay."; }
  }
}
function clearFile() { fileIn.value = ""; chip.hidden = true; drop.hidden = false; detectSeq++; clearAuto(); }

$("#pickBtn").addEventListener("click", () => fileIn.click());
fileIn.addEventListener("change", () => acceptFile(fileIn.files[0]));
$("#fcClear").addEventListener("click", clearFile);
["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, () => drop.classList.remove("over")));
drop.addEventListener("drop", e => { e.preventDefault(); acceptFile(e.dataTransfer.files[0]); });
$("#uploadReset").addEventListener("click", () => { form.reset(); clearFile(); setFileErr(""); setUploadErr(""); });

form.addEventListener("submit", e => {
  e.preventDefault();
  if (A.uploading) return;
  setUploadErr("");
  const file = fileIn.files[0];
  if (!file) return setFileErr("Vui lòng chọn tệp văn bản.");
  if (!$("#u_doc_type").value) return setUploadErr("Hãy chọn loại văn bản.");

  const fd = new FormData(form);
  const btn = $("#uploadBtn"), lbl = btn.querySelector("span");
  A.uploading = true; btn.disabled = true; lbl.textContent = "Đang tải lên… 0%";
  const xhr = new XMLHttpRequest();
  xhr.open("POST", "/api/admin/documents");
  xhr.setRequestHeader("X-Requested-With", "cg");
  xhr.upload.onprogress = ev => { if (ev.lengthComputable) lbl.textContent = `Đang tải lên… ${Math.round(ev.loaded / ev.total * 100)}%`; };
  const done = () => { A.uploading = false; btn.disabled = false; lbl.textContent = "Tải lên và lập chỉ mục"; };
  xhr.onerror = () => { done(); setUploadErr("Không kết nối được tới máy chủ. Dữ liệu bạn nhập vẫn được giữ lại."); };
  xhr.onload = () => {
    done();
    let j = {}; try { j = JSON.parse(xhr.responseText); } catch {}
    if (xhr.status >= 200 && xhr.status < 300) {
      form.reset(); clearFile(); A.filter = "all"; toast(`Đã tải lên, “${j.title || file.name}” đang được xử lý.`, "ok"); loadDocs(true);
    } else if (xhr.status === 401) { location.href = "/login?next=/admin"; }
    else if (xhr.status === 403) { setUploadErr("Bạn không còn quyền quản trị dữ liệu."); }
    else {
      const msg = typeof j.detail === "string" ? j.detail : Array.isArray(j.detail) ? j.detail.map(x => x.msg).join("; ") : `Lỗi ${xhr.status}.`;
      setUploadErr(msg);
    }
  };
  xhr.send(fd);
});

/* ---------- Sửa thông tin ---------- */
const FIELDS = ["title", "doc_type", "number", "issuer", "validity", "issued_date", "effective_date", "replaced_by", "notes"];
function openEdit(d) {
  A.editId = d.id;
  FIELDS.forEach(k => { $("#e_" + k).value = d[k] || ""; });
  $("#editErr").hidden = true;
  $("#editDlg").showModal();
}
$("#editCancel").addEventListener("click", () => $("#editDlg").close());
$("#editForm").addEventListener("submit", async e => {
  e.preventDefault();
  const body = {}; FIELDS.forEach(k => { body[k] = $("#e_" + k).value; });
  try {
    await api(`/api/admin/documents/${A.editId}`, { method: "PATCH", body });
    $("#editDlg").close(); toast("Đã cập nhật thông tin", "ok"); loadDocs(true);
  } catch (err) {
    if (unauthorized(err)) { $("#editDlg").close(); return; }
    $("#editErr").textContent = err.message; $("#editErr").hidden = false;
  }
});

/* ---------- Thay file ---------- */
$("#replaceInput").addEventListener("change", async e => {
  const file = e.target.files[0]; if (!file) return;
  const d = A.docs.find(x => x.id === A.replaceId);
  const ext = "." + file.name.split(".").pop().toLowerCase();
  if (!allowedExt().includes(ext)) return toast(`Định dạng ${ext} không được hỗ trợ.`, "err");
  if (file.size > maxMb() * 1048576) return toast(`File vượt quá ${maxMb()} MB.`, "err");
  if (!await confirmBox("Thay file tài liệu?", `File của "${d.title}" sẽ được thay bằng "${file.name}". Tài liệu tạm thời rời khỏi chỉ mục cho đến khi xử lý xong. Không thể hoàn tác.`, "Thay file")) return;
  const fd = new FormData(); fd.append("file", file);
  try {
    await api(`/api/admin/documents/${A.replaceId}/replace`, { method: "POST", form: fd });
    toast("Đã thay file, hệ thống đang xử lý lại", "ok"); loadDocs(true);
  } catch (err) { if (!unauthorized(err)) toast(err.message, "err"); }
});

function init() { loadDocs(); }
renderAll();
init();
