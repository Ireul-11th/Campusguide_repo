/* Trang Hỏi đáp AI */
const TOPICS = [
  { topic: "Học bổng", icon: "award", q: "Điều kiện để xét học bổng là gì?" },
  { topic: "Học lại", icon: "rotate-ccw", q: "Rớt môn thì học lại như thế nào?" },
  { topic: "Học phí", icon: "wallet", q: "Học phí được tính theo tín chỉ như thế nào?" },
  { topic: "Tín chỉ", icon: "layers", q: "Số tín chỉ tối thiểu mỗi học kỳ là bao nhiêu?" },
  { topic: "Tốt nghiệp", icon: "graduation-cap", q: "Điều kiện để được xét tốt nghiệp?" },
  { topic: "Ngoài phạm vi", icon: "search-x", q: "Thời tiết Đà Nẵng hôm nay thế nào?", out: true },
];
const PRINCIPLES = [
  { icon: "quote", t: "Trích dẫn rõ ràng", d: "Mỗi ý đều kèm văn bản, Điều/Khoản và trang." },
  { icon: "badge-check", t: "Ưu tiên văn bản còn hiệu lực", d: "Văn bản đã thay thế được đánh dấu riêng." },
  { icon: "search-x", t: "Không đoán mò", d: "Thiếu căn cứ thì hệ thống nói rõ là không tìm thấy." },
];
const DOWN_REASONS = ["Sai thông tin", "Thiếu nguồn", "Khó hiểu", "Không đúng câu hỏi"];

const state = {
  convId: null,
  msgs: [],      // {role, content, status, sources, warnings, id, feedback, feedback_reason, error, elapsed}
  src: null,     // {msg, n}: nguồn đang mở trong sheet (msg = chỉ số tin nhắn, n = chỉ số nguồn 0..)
  busy: false,
  convs: [],
  hq: "",
};

const el = {
  messages: $("#messages"), q: $("#q"), form: $("#composer"), send: $("#sendBtn"), counter: $("#counter"),
  scrim: $("#scrim"), histSheet: $("#histSheet"), srcSheet: $("#srcSheet"),
  title: $("#convTitle"), newBtn: $("#newChat"), label: $("#qLabel"),
};
const norm = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/đ/g, "d").replace(/Đ/g, "D").toLowerCase();

/* ---------- Lớp phủ (sheet) ---------- */
let lastFocus = null;
function openSheet(sheet) {
  lastFocus = document.activeElement;
  sheet.classList.add("open"); sheet.setAttribute("aria-hidden", "false");
  el.scrim.classList.add("open");
  (sheet.querySelector("[data-close]") || sheet).focus?.();
}
function closeSheets() {
  [el.histSheet, el.srcSheet].forEach(s => { s.classList.remove("open"); s.setAttribute("aria-hidden", "true"); });
  el.scrim.classList.remove("open");
  lastFocus?.focus?.(); lastFocus = null;
}
el.scrim.addEventListener("click", closeSheets);
$$("[data-close]").forEach(b => b.addEventListener("click", closeSheets));
document.addEventListener("keydown", e => { if (e.key === "Escape" && el.scrim.classList.contains("open")) closeSheets(); });

/* ---------- Hiển thị câu trả lời ---------- */
function inline(text, nSrc) {
  let t = esc(text).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  return t.replace(/\[(\d{1,2})\]/g, (m, n) => (+n >= 1 && +n <= nSrc)
    ? `<button type="button" class="cite" data-n="${n}" aria-label="Xem nguồn ${n}">${n}</button>` : m);
}

function renderMarkdown(text, nSrc) {
  const out = [];
  let list = null;
  const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) { close(); continue; }
    let m;
    if ((m = /^[-*•]\s+(.*)$/.exec(line))) {
      if (list !== "ul") { close(); out.push("<ul>"); list = "ul"; }
      out.push(`<li>${inline(m[1], nSrc)}</li>`);
    } else if ((m = /^\d+[.)]\s+(.*)$/.exec(line))) {
      if (list !== "ol") { close(); out.push("<ol>"); list = "ol"; }
      out.push(`<li>${inline(m[1], nSrc)}</li>`);
    } else {
      close();
      const h = /^#{1,4}\s+(.*)$/.exec(line);
      out.push(h ? `<p><strong>${inline(h[1], nSrc)}</strong></p>` : `<p>${inline(line, nSrc)}</p>`);
    }
  }
  close();
  return out.join("");
}

function where(s) {
  const bits = [];
  if (s.chapter) bits.push(s.chapter);
  if (s.article) bits.push(`Điều ${s.article}`);
  return bits.join(" · ");
}
function srcLine(s) {
  const bits = [where(s)];
  bits.push(s.page ? `tr. ${s.page}` : "");
  return bits.filter(Boolean).join(" · ") || "Đoạn trích";
}

function sourcesGrid(m, i) {
  return `<section class="srcs" aria-label="Nguồn trích dẫn">
    <h3 class="label-s" style="display:flex;align-items:center;gap:6px;font-family:var(--sans);font-weight:600">${ic("book-open-check", "sm")}Nguồn đối chiếu</h3>
    <ol>${m.sources.map((s, k) => `<li><button type="button" data-act="src" data-i="${i}" data-k="${k}">
      <span class="n">${k + 1}</span>
      <span class="tx"><b>${esc(s.doc_title)}</b><small>${esc(srcLine(s))}</small></span>${ic("file-search")}
      <span class="sr-only">Mở đoạn trích</span></button></li>`).join("")}</ol></section>`;
}

function feedbackBar(m, i) {
  if (!m.id) return "";
  const up = m.feedback === 1, down = m.feedback === -1;
  return `<div class="ans-foot">
    <span class="q">Câu trả lời này có hữu ích?</span>
    <button class="btn sm ghost ${up ? "on" : ""}" data-act="up" data-i="${i}" aria-pressed="${up}">${ic("thumbs-up")}Hữu ích</button>
    <button class="btn sm ghost ${down ? "on neg" : ""}" data-act="down" data-i="${i}" aria-pressed="${down}">${ic("thumbs-down")}Chưa hữu ích</button>
    <button class="btn sm ghost sp" data-act="copy" data-i="${i}">${ic("copy")}Sao chép</button>
  </div>${down ? (m.feedback_reason
    ? `<div class="reasons" role="status"><p class="hint" style="font-size:14px">Đã ghi nhận: <strong style="color:var(--fg)">${esc(m.feedback_reason)}</strong>. Phản hồi giúp cải thiện dữ liệu.</p></div>`
    : `<fieldset class="reasons" style="border:0;border-top:1px solid var(--border)"><legend class="sr-only">Điều gì chưa ổn?</legend><span style="font-size:14px;font-weight:500">Điều gì chưa ổn?</span>
       <div>${DOWN_REASONS.map(r => `<button type="button" data-act="reason" data-i="${i}" data-r="${esc(r)}">${esc(r)}</button>`).join("")}</div></fieldset>`) : ""}`;
}

function followUps(label, items) {
  return `<div class="follow"><p class="label-s">${esc(label)}</p><div>${items.map((q, k) =>
    `<button type="button" class="rise" data-act="ask" data-q="${esc(q)}" style="animation-delay:${120 + k * 60}ms">${ic("corner-down-right", "sm")}${esc(q)}</button>`).join("")}</div></div>`;
}

function answerCard(m, i) {
  const n = m.sources.length;
  const docs = new Set(m.sources.map(s => s.doc_id)).size;
  const warn = m.warnings.map(w => `<div class="msg-warn">${ic("triangle-alert")}<span>${esc(w)}</span></div>`).join("");
  const time = m.elapsed ? ` · ${(m.elapsed / 1000).toFixed(1).replace(".", ",")} giây` : "";
  return `<div class="ans">
    <div class="ans-head"><span class="ok">${ic("shield-check", "sm")}Có căn cứ</span>
      <span class="meta">${n} trích dẫn · ${docs} văn bản${time}</span></div>
    <div class="ans-body">${renderMarkdown(m.content, n)}</div>${warn}
    ${n ? sourcesGrid(m, i) : ""}${feedbackBar(m, i)}</div>`;
}

function botCard(m, i, isLast) {
  switch (m.status) {
    case "ok":
      return answerCard(m, i);
    case "retrieval_only":
      return `<div class="notice-card info"><div class="row"><span class="ico">${ic("info", "lg")}</span><div style="min-width:0;flex:1">
        <h3>Chưa cấu hình LLM nên chưa soạn được câu trả lời</h3>
        <p>Đây là các đoạn quy chế liên quan nhất tìm được. Đặt <code>LLM_PROVIDER</code> và khóa API trong file <code>.env</code> để bật câu trả lời tự động.</p></div></div></div>
        <div class="ans" style="margin-top:12px">${sourcesGrid(m, i)}</div>`;
    case "no_basis":
      return `<div class="notice-card warn"><div class="row"><span class="ico">${ic("search-x", "lg")}</span><div style="min-width:0;flex:1">
        <p class="k">Không đủ căn cứ</p>
        <h3>Không tìm thấy quy định liên quan trong văn bản chính thức</h3>
        <p>CampusGuide đã tìm trong các văn bản đã lập chỉ mục nhưng không có đoạn nào đủ liên quan để trả lời. Để tránh cung cấp thông tin sai, hệ thống <strong>không đưa ra câu trả lời phỏng đoán</strong>.</p>
        <ul><li>${ic("corner-down-right")}<span>Diễn đạt lại câu hỏi với từ khóa cụ thể (ví dụ: tên học phần, loại học bổng).</span></li>
        <li>${ic("corner-down-right")}<span>Tự tra cứu trong <a href="/library" style="font-weight:500">Thư viện văn bản</a>.</span></li>
        <li>${ic("corner-down-right")}<span>Liên hệ phòng Đào tạo hoặc đơn vị phụ trách của trường.</span></li></ul></div></div>
        ${isLast ? followUps("Thử câu hỏi có trong văn bản", TOPICS.filter(t => !t.out).slice(0, 3).map(t => t.q)) : ""}</div>`;
    case "empty_index":
      return `<div class="notice-card warn"><div class="row"><span class="ico">${ic("inbox", "lg")}</span><div>
        <p class="k">Chưa có dữ liệu</p><h3>Chưa có tài liệu nào được lập chỉ mục</h3>
        <p>Hãy tải văn bản ở trang <a href="/admin" style="font-weight:500">Quản trị dữ liệu</a> trước khi đặt câu hỏi.</p></div></div></div>`;
    case "llm_error":
      return `<div class="notice-card bad" role="alert"><div class="row"><span class="ico">${ic("triangle-alert", "lg")}</span><div style="min-width:0;flex:1">
        <h3 style="color:var(--danger)">Không soạn được câu trả lời</h3>
        <p>${esc(m.error || "Dịch vụ LLM đang lỗi")}. Các đoạn liên quan vẫn được liệt kê bên dưới.</p>
        <div class="btns"><button class="btn lg" data-act="retry" data-i="${i}">${ic("rotate-ccw")}Thử lại</button></div></div></div></div>
        ${m.sources.length ? `<div class="ans" style="margin-top:12px">${sourcesGrid(m, i)}</div>` : ""}`;
    case "client_error":
      return `<div class="notice-card bad" role="alert"><div class="row"><span class="ico">${ic("triangle-alert", "lg")}</span><div style="min-width:0;flex:1">
        <h3 style="color:var(--danger)">Không kết nối được tới máy chủ tra cứu</h3>
        <p>${esc(m.content)} Câu hỏi chưa được xử lý, không có câu trả lời nào được tạo.</p>
        <div class="btns"><button class="btn lg" data-act="retry" data-i="${i}">${ic("rotate-ccw")}Thử lại</button></div></div></div></div>`;
    case "typing": {
      const stage = Math.min(m.stage || 0, STAGES.length - 1);
      const items = STAGES.map((lb, k) => {
        const st = k < stage ? "done" : k === stage ? "active" : "todo";
        const mark = st === "done" ? ic("check", "sm") : st === "active" ? `<span class="spin" aria-hidden="true"></span>` : "";
        return `<li class="${st}"><span class="dot">${mark}</span>${lb}<span class="sr-only">${st === "done" ? " (xong)" : st === "active" ? " (đang thực hiện)" : " (chờ)"}</span></li>`;
      }).join("");
      return `<div class="pending" aria-busy="true"><div class="scan"><i></i></div><div class="in">
        <div class="st" role="status"><span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>CampusGuide đang tra cứu…</div>
        <ol class="stages">${items}</ol>
        <div class="sk" aria-hidden="true"><div class="skel" style="width:92%"></div><div class="skel" style="width:80%"></div><div class="skel" style="width:66%"></div></div></div></div>`;
    }
  }
  return `<div class="ans"><div class="ans-body">${esc(m.content)}</div></div>`;
}

function welcome() {
  const h = CG.health;
  const stat = h ? (h.index.docs ? `${h.index.docs} văn bản đã lập chỉ mục · ${h.index.chunks} đoạn` : "Chưa có văn bản nào được lập chỉ mục") : "Đang kiểm tra dữ liệu…";
  return `<div class="welcome">
    <p class="chip-top rise">${ic("calendar-clock", "sm")}${esc(stat)}</p>
    <h2 class="hl rise" style="animation-delay:60ms">Hỏi về quy chế đào tạo, nhận câu trả lời <em>có căn cứ</em>.</h2>
    <p class="lead rise" style="animation-delay:120ms">Đặt câu hỏi bằng tiếng Việt tự nhiên. CampusGuide tìm đoạn liên quan trong quy chế, quy định, thông báo chính thức của trường và trả lời kèm nguồn để bạn tự đối chiếu.</p>
    <ul class="principles rise" style="animation-delay:180ms">${PRINCIPLES.map(p => `<li>${ic(p.icon)}<div><b>${esc(p.t)}</b><span>${esc(p.d)}</span></div></li>`).join("")}</ul>
    <section aria-labelledby="goiy" style="margin-top:32px"><h2 id="goiy" class="label-s" style="font-family:var(--sans);font-weight:600;font-size:12px">Câu hỏi gợi ý</h2>
    <ul class="sugg">${TOPICS.map((t, k) => `<li class="rise" style="animation-delay:${240 + k * 50}ms"><button type="button" data-act="ask" data-q="${esc(t.q)}">
      <span class="ico ${t.out ? "w" : ""}">${ic(t.icon)}</span>
      <span style="min-width:0;flex:1"><small>${esc(t.topic)}${t.out ? " – xem cách hệ thống từ chối đoán" : ""}</small><span class="q">${esc(t.q)}</span></span>
      <span class="go">${ic("arrow-up-right")}</span></button></li>`).join("")}</ul></section></div>`;
}

const STAGES = ["Phân tích câu hỏi", "Tìm đoạn liên quan trong văn bản", "Đối chiếu Chương / Điều / Khoản", "Soạn câu trả lời kèm trích dẫn"];

function renderMessages(scroll = "bottom") {
  el.title.textContent = state.convId ? (state.convs.find(c => c.id === state.convId)?.title || "Hội thoại") : "Cuộc hỏi đáp mới";
  el.newBtn.hidden = !state.msgs.length;
  el.label.textContent = state.msgs.length ? "Hỏi tiếp hoặc đặt câu hỏi mới" : "Câu hỏi của bạn về quy chế, học vụ";
  if (!state.msgs.length) { el.messages.innerHTML = welcome(); return; }
  const keep = el.messages.scrollTop;
  let html = "";
  state.msgs.forEach((m, i) => {
    if (m.role === "user") {
      html += `<article class="turn" data-i="${i}" aria-labelledby="q${i}"><div class="turn-q"><span class="avatar" aria-hidden="true">SV</span>
        <div style="min-width:0"><p class="k">Câu hỏi</p><h2 id="q${i}">${esc(m.content)}</h2></div></div><div class="turn-a">`;
    } else {
      const isLast = i === state.msgs.length - 1;
      html += `<div data-i="${i}">${botCard(m, i, isLast)}</div></div></article>`;
    }
  });
  if (state.msgs[state.msgs.length - 1]?.role === "user") html += "</div></article>";
  el.messages.innerHTML = `<div class="thread">${html}</div>`;
  if (scroll === "bottom") {
    const turns = $$(".turn", el.messages);
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    turns[turns.length - 1]?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
  } else el.messages.scrollTop = keep;
}

/* ---------- Sheet nguồn ---------- */
function highlight(text, terms) {
  if (!terms || !terms.length) return esc(text);
  const alt = terms.map(t => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|");
  const re = new RegExp(`(?<![\\p{L}\\p{N}])(${alt})(?![\\p{L}\\p{N}])`, "giu");
  let out = "", last = 0, m;
  while ((m = re.exec(text))) {
    out += esc(text.slice(last, m.index)) + "<mark>" + esc(m[0]) + "</mark>";
    last = m.index + m[0].length;
  }
  return out + esc(text.slice(last));
}

function renderSource() {
  const { msg, n } = state.src;
  const srcs = state.msgs[msg].sources;
  const s = srcs[n];
  $("#srcTitle").textContent = s.doc_title;
  $("#srcDesc").textContent = [s.doc_number && `Số hiệu ${s.doc_number}`, CG.docTypes[s.doc_type] || "Khác", s.issued_date && `ban hành ${fmtDate(s.issued_date)}`].filter(Boolean).join(" · ");

  const tabs = $("#srcTabs");
  tabs.hidden = srcs.length < 2;
  tabs.innerHTML = srcs.map((x, k) => `<button role="tab" type="button" data-k="${k}" aria-selected="${k === n}"><span class="tnum">[${k + 1}]</span><span class="tt">${esc(x.doc_title)}</span></button>`).join("");

  const crumbs = [s.chapter, s.article && `Điều ${s.article}`].filter(Boolean);
  const heading = s.article ? `Điều ${s.article}${s.article_title ? ". " + s.article_title : ""}` : (s.article_title || "Đoạn trích");
  const open = s.file_url
    ? `<a class="btn lg" target="_blank" rel="noopener" href="${s.file_url}${s.is_pdf && s.page ? "#page=" + s.page : ""}">${ic("external-link")}Mở văn bản gốc</a>`
    : `<span class="hint">Văn bản gốc không còn trong thư viện.</span>`;
  const lib = s.file_url ? `<a class="btn lg primary" href="/library/${s.doc_id}#c${s.chunk_id}">${ic("library")}Mở trong thư viện</a>` : "";
  $("#srcBody").innerHTML = `
    <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center">${validityBadge(s.validity, s.validity_label)}
      ${s.is_reference ? '<span class="badge info">Điều được dẫn tới</span>' : ""}
      ${s.replaced_by ? `<span class="badge warn">Thay thế: ${esc(s.replaced_by)}</span>` : ""}</div>
    <ol class="crumbs" aria-label="Vị trí trong văn bản">${crumbs.map((c, k) => `<li>${esc(c)}${k < crumbs.length - 1 ? ic("chevron-right", "sm") : ""}</li>`).join("")}
      <li class="pg">${s.page ? `Trang ${s.page}` : "Chưa có thông tin trang"}</li></ol>
    <figure class="quote" style="margin-left:0;margin-right:0"><small class="t">${esc(heading)}</small>
      <blockquote>${highlight(s.text, s.highlight)}</blockquote>
      <figcaption>${ic("file-text", "sm")}${esc(s.doc_title)}${s.page ? ` · tr. ${s.page}` : ""}</figcaption></figure>
    <p class="sheet-note">Phần tô sáng là từ khóa trong câu hỏi xuất hiện ở đoạn này. Luôn đối chiếu với văn bản gốc trước khi dùng cho thủ tục chính thức.</p>
    <div class="sheet-acts">${lib}${open}<button type="button" class="btn lg" data-act="copycite">${ic("copy")}Sao chép trích dẫn</button></div>`;
  $("#srcBody").style.animation = "none"; void $("#srcBody").offsetWidth; $("#srcBody").style.animation = "";
  $("#srcBody").scrollTop = 0;

  const foot = $("#srcFoot");
  foot.hidden = srcs.length < 2;
  foot.innerHTML = `<button type="button" class="btn ghost sm" data-step="-1" ${n === 0 ? "disabled" : ""}>${ic("chevron-left")}Nguồn trước</button>
    <span class="tnum">${n + 1} / ${srcs.length}</span>
    <button type="button" class="btn ghost sm" data-step="1" ${n === srcs.length - 1 ? "disabled" : ""}>Nguồn sau${ic("chevron-right")}</button>`;
}

function openSource(msg, n) {
  state.src = { msg, n };
  renderSource();
  if (!el.srcSheet.classList.contains("open")) openSheet(el.srcSheet);
}

$("#srcTabs").addEventListener("click", e => { const b = e.target.closest("[data-k]"); if (b) { state.src.n = +b.dataset.k; renderSource(); } });
$("#srcFoot").addEventListener("click", e => { const b = e.target.closest("[data-step]"); if (b && !b.disabled) { state.src.n += +b.dataset.step; renderSource(); } });
$("#srcBody").addEventListener("click", async e => {
  if (!e.target.closest("[data-act=copycite]")) return;
  const s = state.msgs[state.src.msg].sources[state.src.n];
  const txt = `${s.doc_title}${s.doc_number ? ", số " + s.doc_number : ""}${where(s) ? ", " + where(s) : ""}${s.page ? ", tr. " + s.page : ""}: “${s.text.trim()}”`;
  await copyText(txt, "Đã sao chép trích dẫn");
});

/* ---------- Lịch sử hội thoại ---------- */
function groupOf(updated) {
  const d = new Date((updated || "").replace(" ", "T") + "Z");
  if (isNaN(d)) return "Trước đó";
  const today = new Date(); today.setHours(0, 0, 0, 0);
  const day = new Date(d); day.setHours(0, 0, 0, 0);
  const diff = Math.round((today - day) / 86400000);
  return diff <= 0 ? "Hôm nay" : diff === 1 ? "Hôm qua" : diff < 7 ? "7 ngày qua" : "Trước đó";
}
function timeOf(updated) {
  const d = new Date((updated || "").replace(" ", "T") + "Z");
  if (isNaN(d)) return "";
  return groupOf(updated) === "Hôm nay" || groupOf(updated) === "Hôm qua"
    ? d.toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString("vi-VN", { day: "2-digit", month: "2-digit" });
}

function renderConvs() {
  const q = norm(state.hq);
  const list = state.convs.filter(c => norm(c.title).includes(q));
  let html;
  if (!list.length) {
    html = `<p class="muted" style="padding:24px 8px;text-align:center;font-size:14px">${state.convs.length ? "Không có cuộc hỏi đáp phù hợp." : "Chưa có cuộc hỏi đáp nào. Câu hỏi đầu tiên của bạn sẽ được lưu ở đây."}</p>`;
  } else {
    const groups = [...new Set(list.map(c => groupOf(c.updated_at)))];
    html = groups.map(g => `<p class="hist-grp">${g}</p>` + list.filter(c => groupOf(c.updated_at) === g).map(c => `
      <div class="conv ${c.id === state.convId ? "active" : ""}" data-id="${c.id}">
        <button class="t" data-act="open" title="${esc(c.title)}" ${c.id === state.convId ? 'aria-current="true"' : ""}>${ic("messages-square")}<span><span class="tt">${esc(c.title)}</span><small>${esc(timeOf(c.updated_at))}</small></span></button>
        <span class="acts"><button class="btn ghost icon" data-act="rename" aria-label="Đổi tên: ${esc(c.title)}">${ic("pencil", "sm")}</button>
        <button class="btn ghost icon" data-act="del" aria-label="Xóa: ${esc(c.title)}">${ic("trash", "sm")}</button></span>
      </div>`).join("")).join("");
  }
  $$(".js-hlist").forEach(n => n.innerHTML = html);
}

async function loadConvs() {
  try {
    state.convs = await api("/api/conversations");
    renderConvs();
    el.title.textContent = state.convId ? (state.convs.find(c => c.id === state.convId)?.title || "Hội thoại") : "Cuộc hỏi đáp mới";
  } catch (e) {
    $$(".js-hlist").forEach(n => n.innerHTML = `<div style="padding:16px 8px;font-size:14px"><strong>Không tải được lịch sử</strong><br><span class="muted">${esc(e.message)}</span><br><button class="btn sm js-hretry" style="margin-top:8px">Thử lại</button></div>`);
  }
}

async function openConv(id) {
  try {
    const c = await api(`/api/conversations/${id}`);
    state.convId = c.id;
    state.msgs = c.messages.map(m => ({ ...m, sources: m.sources || [], warnings: m.warnings || [] }));
    try {  // nguồn của văn bản đã bị xóa thì không còn link tới bản gốc
      const alive = new Set((await api("/api/documents")).map(d => d.id));
      state.msgs.forEach(m => (m.sources || []).forEach(s => { if (!alive.has(s.doc_id)) s.file_url = ""; }));
    } catch {}
    renderMessages("top"); renderConvs();
    el.messages.scrollTop = el.messages.scrollHeight;
    closeSheets();
  } catch (e) { toast(e.message, "err"); }
}

function newChat() {
  state.convId = null; state.msgs = []; state.src = null;
  renderMessages("top"); renderConvs();
  closeSheets();
  el.q.focus();
}

/* ---------- Gửi câu hỏi ---------- */
function updateSend() {
  const ok = el.q.value.trim().length > 1 && !state.busy;
  el.send.disabled = !ok;
  el.send.classList.toggle("ready", ok);
  el.send.setAttribute("aria-label", state.busy ? "Đang trả lời" : "Gửi câu hỏi");
  el.send.innerHTML = state.busy ? ic("loader").replace('class="ic', 'class="ic spin') : ic("arrow-up");
}
function setBusy(b) { state.busy = b; updateSend(); }

async function ask(question, { addUser = true } = {}) {
  question = question.trim();
  if (state.busy || !question) return;
  if (addUser) state.msgs.push({ role: "user", content: question });
  state.msgs.push({ role: "assistant", status: "typing", content: "", sources: [], warnings: [] });
  setBusy(true); renderMessages();
  const t0 = performance.now();
  const typing = state.msgs[state.msgs.length - 1];
  const tick = setInterval(() => {   // chỉ là gợi ý tiến trình; bước cuối chờ tới khi máy chủ trả lời
    if (typing.stage >= STAGES.length - 1 || !state.msgs.includes(typing)) return;
    typing.stage = (typing.stage || 0) + 1; renderMessages("keep");
  }, 700);
  try {
    const r = await api("/api/chat", { method: "POST", body: { question, conversation_id: state.convId } });
    state.convId = r.conversation_id;
    state.msgs.pop();
    const m = r.message; m.sources = m.sources || []; m.warnings = m.warnings || []; m.error = r.error; m.question = question;
    m.elapsed = performance.now() - t0;
    state.msgs.push(m);
    renderMessages();
    await loadConvs();
  } catch (e) {
    state.msgs.pop();
    state.msgs.push({ role: "assistant", status: "client_error", content: e.message, sources: [], warnings: [], question });
    renderMessages();
  } finally { clearInterval(tick); setBusy(false); }
}

function lastQuestionBefore(i) {
  for (let k = i - 1; k >= 0; k--) if (state.msgs[k].role === "user") return state.msgs[k].content;
  return "";
}

async function copyText(text, okMsg = "Đã sao chép câu trả lời kèm nguồn") {
  try { await navigator.clipboard.writeText(text); toast(okMsg, "ok"); return; } catch {}
  try {
    const ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select();
    const ok = document.execCommand("copy"); ta.remove();
    ok ? toast(okMsg, "ok") : toast("Không sao chép được, hãy bôi đen và sao chép thủ công.", "err");
  } catch { toast("Không sao chép được, hãy bôi đen và sao chép thủ công.", "err"); }
}

function plainAnswer(m, i) {
  const body = m.content.replace(/\*\*/g, "");
  const src = m.sources.map((s, k) => `[${k + 1}] ${s.doc_title}${s.doc_number ? " (" + s.doc_number + ")" : ""} – ${srcLine(s)}`).join("\n");
  return `Hỏi: ${m.question || lastQuestionBefore(i)}\n\n${body}\n\nNguồn:\n${src}\n\n(CampusGuide AI)`;
}

async function sendFeedback(m, value, reason = "") {
  await api(`/api/messages/${m.id}/feedback`, { method: "POST", body: { value, reason } });
  m.feedback = value; m.feedback_reason = reason;
}

/* ---------- Sự kiện ---------- */
el.form.addEventListener("submit", e => {
  e.preventDefault();
  const q = el.q.value.trim();
  if (q.length < 2 || state.busy) return;
  el.q.value = ""; autoGrow();
  ask(q);
});
el.q.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing && e.keyCode !== 229) { e.preventDefault(); el.form.requestSubmit(); }
});
function autoGrow() {
  el.q.style.height = "auto";
  el.q.style.height = Math.min(Math.max(el.q.scrollHeight, 44), 160) + "px";
  el.counter.textContent = `${el.q.value.length}/1000`;
  updateSend();
}
el.q.addEventListener("input", autoGrow);

el.messages.addEventListener("click", async e => {
  const cite = e.target.closest(".cite");
  if (cite) { openSource(+cite.closest("[data-i]").dataset.i, +cite.dataset.n - 1); return; }
  const b = e.target.closest("[data-act]");
  if (!b) return;
  const act = b.dataset.act;
  if (act === "ask") { ask(b.dataset.q); return; }
  const i = +b.dataset.i, m = state.msgs[i];
  switch (act) {
    case "src": openSource(i, +b.dataset.k); break;
    case "copy": copyText(plainAnswer(m, i)); break;
    case "retry": {
      const q = m.question || lastQuestionBefore(i);
      state.msgs.splice(i, 1);
      ask(q, { addUser: false }); break;
    }
    case "up": case "down": {
      const v = act === "up" ? 1 : -1;
      const nv = m.feedback === v ? 0 : v;
      try { await sendFeedback(m, nv); renderMessages("keep"); if (nv === 1) toast("Cảm ơn bạn đã đánh giá!", "ok"); }
      catch (err) { toast("Chưa gửi được phản hồi: " + err.message, "err"); }
      break;
    }
    case "reason":
      try { await sendFeedback(m, -1, b.dataset.r); renderMessages("keep"); }
      catch (err) { toast("Chưa gửi được phản hồi: " + err.message, "err"); }
      break;
  }
});

document.addEventListener("click", async e => {
  const root = e.target.closest(".hist, #histSheet");
  if (!root) return;
  if (e.target.closest(".js-new")) { newChat(); return; }
  if (e.target.closest(".js-hretry")) { loadConvs(); return; }
  const item = e.target.closest(".conv"); if (!item) return;
  const id = +item.dataset.id, act = e.target.closest("[data-act]")?.dataset.act;
  if (act === "open") { if (state.busy) { toast("Đang trả lời, vui lòng chờ xong rồi chuyển hội thoại.", ""); return; } openConv(id); }
  if (act === "rename") {
    const cur = state.convs.find(c => c.id === id)?.title || "";
    const t = prompt("Tên mới cho hội thoại:", cur);
    if (t && t.trim()) {
      try { await api(`/api/conversations/${id}`, { method: "PATCH", body: { title: t.trim() } }); loadConvs(); }
      catch (err) { toast(err.message, "err"); }
    }
  }
  if (act === "del") {
    if (await confirmBox("Xóa hội thoại?", "Hội thoại và các câu trả lời trong đó sẽ bị xóa vĩnh viễn.", "Xóa")) {
      try { await api(`/api/conversations/${id}`, { method: "DELETE" }); if (id === state.convId) newChat(); loadConvs(); }
      catch (err) { toast(err.message, "err"); }
    }
  }
});
$$(".js-hsearch").forEach(inp => inp.addEventListener("input", () => {
  state.hq = inp.value; $$(".js-hsearch").forEach(o => { if (o !== inp) o.value = inp.value; }); renderConvs();
}));

el.newBtn.addEventListener("click", newChat);
$("#histBtn").addEventListener("click", () => openSheet(el.histSheet));
document.addEventListener("cg:health", () => { if (!state.msgs.length) renderMessages("top"); });

/* Điền sẵn câu hỏi khi đến từ trang văn bản: /?q=... */
(() => {
  const q = new URLSearchParams(location.search).get("q");
  if (q) { el.q.value = q.slice(0, 1000); history.replaceState(null, "", "/"); }
})();

renderMessages("top"); renderConvs(); loadConvs(); autoGrow();
if (el.q.value) { el.q.focus(); el.q.setSelectionRange(el.q.value.length, el.q.value.length); }
