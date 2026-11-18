/* Trang chi tiết một văn bản */
(async () => {
  const root = $("#docRoot");
  const back = `<a class="back" href="/library">${ic("arrow-left")}Thư viện văn bản</a>`;
  const notFound = (msg) => {
    root.innerHTML = `${back}<div class="nf">
      <span class="ico">${ic("file-question", "xl")}</span><h1>Không tìm thấy văn bản</h1>
      <p>${esc(msg || "Đường dẫn có thể đã thay đổi, hoặc văn bản đã được gỡ khỏi thư viện.")}</p>
      <div class="btns"><a class="btn primary lg" href="/library">Về Thư viện</a><a class="btn lg" href="/">Hỏi đáp AI</a></div></div>`;
    document.title = "Không tìm thấy văn bản · CampusGuide AI";
  };
  root.innerHTML = `${back}<div style="margin-top:24px"><div class="skel" style="height:14px;width:160px"></div><div class="skel" style="height:28px;width:70%;margin-top:12px"></div><div class="skel" style="height:14px;width:50%;margin-top:12px"></div></div>`;
  let d;
  try { d = await api(`/api/documents/${CG.docId}`); }
  catch (e) {
    if (e.status === 404) return notFound();
    root.innerHTML = `${back}<div class="error-state" role="alert" style="margin-top:24px"><span class="ico">${ic("triangle-alert", "lg")}</span>
      <div><b>Không tải được văn bản</b><p>${esc(e.message)}</p></div><button class="btn lg" onclick="location.reload()">${ic("rotate-ccw")}Thử lại</button></div>`;
    return;
  }
  if (d.proc_status !== "done") return notFound("Văn bản này chưa được lập chỉ mục xong.");
  document.title = `${d.title} · CampusGuide AI`;

  const meta = [
    ["Số hiệu", d.number || "Chưa có thông tin"],
    ["Loại văn bản", d.doc_type_label],
    ["Cơ quan ban hành", d.issuer || "Chưa có thông tin"],
    ["Ngày ban hành", fmtDate(d.issued_date) || "Chưa có thông tin"],
    ["Ngày hiệu lực", fmtDate(d.effective_date) || "Chưa có thông tin"],
    ["Số trang", d.pages ? `${d.pages} trang` : "Không có (DOCX/TXT)"],
    ["Đã lập chỉ mục", `${d.n_chunks} đoạn`],
  ];
  if (d.replaced_by) meta.push(["Văn bản thay thế", d.replaced_by]);

  const warn = d.validity === "het_hieu_luc" ? `<strong style="color:var(--warning)">Văn bản đã hết hiệu lực.</strong> Hãy đối chiếu với văn bản mới trước khi áp dụng.`
    : d.validity === "da_thay_the" ? `<strong style="color:var(--warning)">Văn bản đã bị thay thế.</strong> Hệ thống ưu tiên văn bản còn hiệu lực khi trả lời.`
    : d.validity === "mot_phan" ? `<strong style="color:var(--warning)">Văn bản còn hiệu lực một phần.</strong> Một số điều khoản đã được sửa đổi bởi văn bản khác.`
    : d.validity === "chua_xac_minh" ? `<strong style="color:var(--warning)">Chưa xác minh hiệu lực.</strong> Quản trị viên chưa xác nhận văn bản này còn hiệu lực hay không.` : "";
  const warnBar = warn ? `<div class="note-bar" role="note">${ic("triangle-alert", "lg")}<p>${warn}${d.replaced_by ? ` Ghi chú: ${esc(d.replaced_by)}.` : ""}</p></div>` : "";

  const secRef = c => [c.chapter, c.article && `Điều ${c.article}`].filter(Boolean).join(" · ") || `Đoạn ${c.ord + 1}`;
  const secTitle = c => c.article ? (c.article_title || `Điều ${c.article}`) : (c.article_title || "Nội dung");

  root.innerHTML = `${back}
  <header class="doc-head">
    <div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px"><span class="eyebrow">${esc(d.doc_type_label)}</span>${validityBadge(d.validity, d.validity_label)}</div>
    <h1>${esc(d.title)}</h1>
    ${d.notes ? `<p class="sum">${esc(d.notes)}</p>` : ""}
    <div class="btns">
      <a class="btn primary lg" href="/?q=${encodeURIComponent("Theo " + d.title + ", ")}">${ic("messages-square")}Hỏi về văn bản này</a>
      <a class="btn lg" target="_blank" rel="noopener" href="${d.file_url}">${ic("download")}Mở / tải bản gốc</a>
    </div>
  </header>
  ${warnBar}
  <div class="doc-grid">
    <aside>
      <section aria-labelledby="ttin"><h2 id="ttin" class="label-s" style="font-family:var(--sans)">Thông tin văn bản</h2>
        <dl class="meta-list">${meta.map(([k, v]) => `<div><dt>${esc(k)}</dt><dd>${esc(v)}</dd></div>`).join("")}</dl></section>
      <nav aria-labelledby="mucluc"><h2 id="mucluc" class="label-s" style="font-family:var(--sans)">Mục lục</h2>
        <ol class="toc">${d.chunks.map(c => `<li><a href="#c${c.id}"><small>${esc(c.article ? "Điều " + c.article : (c.chapter || "Đoạn " + (c.ord + 1)))}</small>${esc(secTitle(c))}</a></li>`).join("")}</ol></nav>
    </aside>
    <article aria-label="Nội dung văn bản" style="min-width:0">
      ${d.chunks.length ? d.chunks.map(c => `<section class="sec" id="c${c.id}" aria-labelledby="c${c.id}t">
        <div class="top"><span style="font-weight:500">${esc(secRef(c))}</span><span class="tnum">${c.page ? "Trang " + c.page : ""}</span></div>
        <h3 id="c${c.id}t">${esc(secTitle(c))}</h3><div class="tx">${esc(c.text)}</div></section>`).join("")
        : `<div class="empty-state"><span class="ico">${ic("file-text", "lg")}</span><h3>Văn bản chưa có đoạn nào</h3><p>Hãy thử lập lại chỉ mục ở trang Quản trị dữ liệu.</p></div>`}
    </article>
  </div>`;
  if (location.hash) document.getElementById(location.hash.slice(1))?.scrollIntoView({ block: "start" });
})();
