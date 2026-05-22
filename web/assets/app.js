// 민티스페이스 v0.2 — 좌측 사이드바 + 책갈피 + 카테고리/프로젝트 추가

const HELPER_DEFAULT = ["localhost", "127.0.0.1"].includes(location.hostname)
  ? `${location.protocol}//${location.hostname}:5500`
  : `http://localhost:5500`;
const STATE = {
  helperBase: localStorage.getItem("mintspace_helper") || HELPER_DEFAULT,
  token: localStorage.getItem("mintspace_token") || "",
  data: { categories: [], projects: [], links: [] },
  bookmarks: [],
  connected: false,
};

// ===== 유틸 =====
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

function toast(msg, kind = "ok") {
  const el = document.createElement("div");
  el.className = `toast ${kind}`;
  el.textContent = msg;
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 200);
  }, 2400);
}

async function api(path, opts = {}) {
  const url = `${STATE.helperBase}${path}`;
  const headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
  if (STATE.token) headers["X-Token"] = STATE.token;
  const res = await fetch(url, { ...opts, headers });
  if (!res.ok) {
    let text = "";
    try { const j = await res.json(); text = j.detail || JSON.stringify(j); }
    catch { text = await res.text(); }
    throw new Error(`${res.status} ${text}`);
  }
  return res.json();
}

function relTime(ts) {
  if (!ts) return "";
  const sec = Math.floor(Date.now() / 1000 - ts);
  if (sec < 60) return "방금 전";
  if (sec < 3600) return `${Math.floor(sec / 60)}분 전`;
  if (sec < 86400) return `${Math.floor(sec / 3600)}시간 전`;
  if (sec < 86400 * 7) return `${Math.floor(sec / 86400)}일 전`;
  if (sec < 86400 * 30) return `${Math.floor(sec / 86400 / 7)}주 전`;
  return `${Math.floor(sec / 86400 / 30)}개월 전`;
}

// ===== 연결 / 토큰 =====
async function checkHelper() {
  try {
    const res = await fetch(`${STATE.helperBase}/api/health`);
    if (!res.ok) throw 0;
    await res.json();
    return true;
  } catch { return false; }
}

async function ensureToken() {
  if (STATE.token) return true;
  try {
    const res = await fetch(`${STATE.helperBase}/api/token-bootstrap`);
    if (res.ok) {
      const j = await res.json();
      STATE.token = j.token;
      localStorage.setItem("mintspace_token", STATE.token);
      return true;
    }
  } catch { /* ignore */ }
  showTokenModal();
  return false;
}

function setHelperStatus(ok, label) {
  const el = $("#helper-status");
  el.classList.toggle("ok", ok);
  el.classList.toggle("err", !ok);
  el.querySelector(".label").textContent = label;
  STATE.connected = ok;
  $("#helper-banner").classList.toggle("hidden", ok);
}

function showTokenModal() { $("#token-modal").classList.remove("hidden"); }
function hideTokenModal() { $("#token-modal").classList.add("hidden"); }

// ===== 사이드바 네비 =====
function renderSidebar() {
  const nav = $("#nav-categories");
  nav.innerHTML = "";
  const byCat = {};
  for (const p of STATE.data.projects) (byCat[p.category] ||= []).push(p);

  for (const cat of STATE.data.categories) {
    const count = (byCat[cat.id] || []).length;
    const item = document.createElement("a");
    item.href = `#cat-${cat.id}`;
    item.className = "nav-item";
    item.dataset.cat = cat.id;
    item.innerHTML = `
      <span class="nav-label">${cat.name}</span>
      <span class="nav-count">${count}</span>
    `;
    nav.appendChild(item);
  }

  $("#nav-bookmark-count").textContent = STATE.bookmarks.length || "";
}

// ===== 메인 카테고리 + 카드 =====
function categoryStyle(cat) {
  return {
    "--cat-color": cat.color,
    "--cat-bg": cat.color + "1a",
    "--cat-border": cat.color + "33",
  };
}

function renderCategories() {
  const area = $("#categories-area");
  area.innerHTML = "";
  const byCat = {};
  for (const p of STATE.data.projects) (byCat[p.category] ||= []).push(p);

  for (const cat of STATE.data.categories) {
    const list = byCat[cat.id] || [];
    const section = document.createElement("section");
    section.className = "section";
    section.id = `cat-${cat.id}`;
    Object.entries(categoryStyle(cat)).forEach(([k, v]) => section.style.setProperty(k, v));

    section.innerHTML = `
      <div class="section-header">
        <h2>
          <span class="section-icon">${cat.icon || ""}</span>
          ${cat.name}
        </h2>
        <span class="section-sub">${list.length}개</span>
        <button class="section-action" data-add-prj="${cat.id}">+ 프로젝트</button>
        ${list.length === 0 ? `<button class="section-action" data-del-cat="${cat.id}" title="빈 카테고리 삭제">✕</button>` : ""}
      </div>
      <div class="grid"></div>
    `;
    const grid = section.querySelector(".grid");
    if (list.length === 0) {
      grid.innerHTML = `<div class="empty">아직 프로젝트 없음 · 우측 [+ 프로젝트] 버튼으로 추가</div>`;
    } else {
      list.forEach(p => grid.appendChild(renderCard(p, cat)));
    }
    area.appendChild(section);
  }
}

function renderCard(p, cat) {
  const card = document.createElement("div");
  card.className = "card" + (p.exists === false ? " missing" : "");
  card.dataset.searchKey = `${p.name} ${p.note || ""} ${p.id} ${cat.name}`.toLowerCase();
  card.dataset.pid = p.id;
  card.dataset.cat = p.category;
  card.draggable = true;
  Object.entries(categoryStyle(cat)).forEach(([k, v]) => card.style.setProperty(k, v));

  const deployBadge = p.url ? `<span class="badge">배포</span>` : "";
  const missingBadge = p.exists === false ? `<span class="badge" style="background:#fee2e2;color:#991b1b">없음</span>` : "";
  const meta = p.last_modified ? `<div class="card-meta">최근 수정 ${relTime(p.last_modified)}</div>` : "";

  card.innerHTML = `
    <div class="card-head">
      <div class="card-title">${p.name} ${deployBadge}${missingBadge}</div>
      <button class="card-menu-btn" data-action="delete" title="삭제">×</button>
    </div>
    <div class="card-note">${p.note || ""}</div>
    ${meta}
    <div class="card-path" title="${p.folder}">${p.folder}</div>
    <div class="card-actions">
      <button class="card-btn" data-action="folder" title="파일 탐색기 열기">📂 폴더</button>
      <button class="card-btn primary" data-action="terminal" title="cldp 실행">💬 cldp</button>
      ${p.url ? `<button class="card-btn" data-action="url" title="사이트 열기">🌐 사이트</button>` : ""}
    </div>
  `;

  card.addEventListener("click", async (e) => {
    const btn = e.target.closest("button[data-action]");
    if (!btn) return;
    const action = btn.dataset.action;
    if (action === "delete") {
      if (!confirm(`프로젝트 "${p.name}" 삭제? (폴더는 그대로)`)) return;
      try {
        await api(`/api/projects-meta/${p.id}`, { method: "DELETE" });
        toast("삭제됨");
        await loadProjects();
      } catch (err) { toast("실패: " + err.message, "err"); }
      return;
    }
    if (action === "url") { window.open(p.url, "_blank", "noopener"); return; }
    if (!STATE.connected) return toast("헬퍼가 꺼져 있어", "err");
    btn.disabled = true;
    try {
      if (action === "folder") {
        await api("/api/open-folder", { method: "POST", body: JSON.stringify({ folder: p.folder, project_id: p.id }) });
        toast(`📂 ${p.name} 열림`);
      } else if (action === "terminal") {
        const r = await api("/api/launch-terminal", { method: "POST", body: JSON.stringify({ folder: p.folder, project_id: p.id }) });
        toast(`💬 ${p.name} cldp 시작 (${r.via})`);
      }
    } catch (err) { toast("실패: " + err.message, "err"); }
    finally { btn.disabled = false; }
  });
  return card;
}

// ===== 책갈피 =====
async function loadBookmarks() {
  try {
    const r = await api("/api/bookmarks");
    STATE.bookmarks = r.bookmarks || [];
    renderBookmarks();
    $("#nav-bookmark-count").textContent = STATE.bookmarks.length || "";
  } catch (e) {
    console.error("책갈피 로딩 실패", e);
  }
}

function renderBookmarks() {
  const grid = $("#bookmarks-grid");
  if (!STATE.bookmarks.length) {
    grid.innerHTML = `<div class="empty-bookmark">아직 책갈피 없음 · 위 입력창에 폴더 경로를 붙여넣어봐</div>`;
    return;
  }
  grid.innerHTML = "";
  for (const b of STATE.bookmarks) {
    const card = document.createElement("div");
    card.className = "card" + (b.exists === false ? " missing" : "");
    card.dataset.searchKey = `${b.name} ${b.folder} ${b.note || ""}`.toLowerCase();
    const meta = b.last_modified ? `<div class="card-meta">최근 수정 ${relTime(b.last_modified)}</div>` : "";
    const missing = b.exists === false ? `<span class="badge" style="background:#fee2e2;color:#991b1b">없음</span>` : "";
    card.innerHTML = `
      <div class="card-head">
        <div class="card-title">📌 ${b.name} ${missing}</div>
        <button class="card-menu-btn" data-bm-del="${b.id}" title="책갈피 제거">×</button>
      </div>
      <div class="card-note">${b.note || ""}</div>
      ${meta}
      <div class="card-path" title="${b.folder}">${b.folder}</div>
      <div class="card-actions">
        <button class="card-btn" data-bm-action="folder">📂 폴더</button>
        <button class="card-btn primary" data-bm-action="terminal">💬 cldp</button>
      </div>
    `;
    card.addEventListener("click", async (e) => {
      const delBtn = e.target.closest("[data-bm-del]");
      if (delBtn) {
        try {
          await api(`/api/bookmarks/${b.id}`, { method: "DELETE" });
          toast("책갈피 제거됨");
          await loadBookmarks();
        } catch (err) { toast("실패: " + err.message, "err"); }
        return;
      }
      const actBtn = e.target.closest("[data-bm-action]");
      if (!actBtn) return;
      const action = actBtn.dataset.bmAction;
      if (!STATE.connected) return toast("헬퍼가 꺼져 있어", "err");
      actBtn.disabled = true;
      try {
        if (action === "folder") {
          await api("/api/open-folder", { method: "POST", body: JSON.stringify({ folder: b.folder, project_id: "bookmark-" + b.id }) });
          toast(`📂 ${b.name} 열림`);
        } else if (action === "terminal") {
          const r = await api("/api/launch-terminal", { method: "POST", body: JSON.stringify({ folder: b.folder, project_id: "bookmark-" + b.id }) });
          toast(`💬 ${b.name} cldp 시작 (${r.via})`);
        }
      } catch (err) { toast("실패: " + err.message, "err"); }
      finally { actBtn.disabled = false; }
    });
    grid.appendChild(card);
  }
}

function setupBookmarkInput() {
  const input = $("#bookmark-input");
  const nameInput = $("#bookmark-name-input");
  const btn = $("#bookmark-add-btn");
  async function add() {
    const folder = input.value.trim().replace(/^["']|["']$/g, "");
    if (!folder) { toast("폴더 경로 비어있음", "err"); return; }
    try {
      await api("/api/bookmarks", {
        method: "POST",
        body: JSON.stringify({ folder, name: nameInput.value.trim() || null }),
      });
      input.value = ""; nameInput.value = "";
      toast("📌 책갈피 추가됨");
      await loadBookmarks();
    } catch (err) { toast("실패: " + err.message, "err"); }
  }
  btn.addEventListener("click", add);
  input.addEventListener("keydown", e => { if (e.key === "Enter") add(); });
  nameInput.addEventListener("keydown", e => { if (e.key === "Enter") add(); });
}

// ===== 카테고리 추가 =====
function setupCategoryModal() {
  $("#add-category-btn").addEventListener("click", () => {
    $("#cat-name").value = "";
    $("#cat-icon").value = "📁";
    $("#cat-color").value = "#10b981";
    $("#category-modal").classList.remove("hidden");
    $("#cat-name").focus();
  });
  $("#cat-save").addEventListener("click", async () => {
    const name = $("#cat-name").value.trim();
    if (!name) return toast("이름을 입력해", "err");
    try {
      await api("/api/categories", {
        method: "POST",
        body: JSON.stringify({
          name,
          icon: $("#cat-icon").value.trim() || "📁",
          color: $("#cat-color").value,
        }),
      });
      $("#category-modal").classList.add("hidden");
      toast(`✅ 카테고리 "${name}" 추가됨`);
      await loadProjects();
    } catch (err) { toast("실패: " + err.message, "err"); }
  });
}

// ===== 프로젝트 추가 =====
function setupProjectModal() {
  document.addEventListener("click", (e) => {
    const addBtn = e.target.closest("[data-add-prj]");
    if (addBtn) {
      openProjectModal(addBtn.dataset.addPrj);
      return;
    }
    const delCat = e.target.closest("[data-del-cat]");
    if (delCat) {
      if (!confirm("빈 카테고리 삭제?")) return;
      api(`/api/categories/${delCat.dataset.delCat}`, { method: "DELETE" })
        .then(() => { toast("삭제됨"); loadProjects(); })
        .catch(err => toast("실패: " + err.message, "err"));
    }
  });

  $("#prj-save").addEventListener("click", async () => {
    const name = $("#prj-name").value.trim();
    const category = $("#prj-category").value;
    const folder = $("#prj-folder").value.trim().replace(/^["']|["']$/g, "");
    if (!name || !folder) return toast("이름과 폴더 경로 필수", "err");
    try {
      await api("/api/projects-meta", {
        method: "POST",
        body: JSON.stringify({
          name, category, folder,
          url: $("#prj-url").value.trim() || null,
          note: $("#prj-note").value.trim() || null,
        }),
      });
      $("#project-modal").classList.add("hidden");
      toast(`✅ 프로젝트 "${name}" 추가됨`);
      await loadProjects();
    } catch (err) { toast("실패: " + err.message, "err"); }
  });
}

function openProjectModal(categoryId) {
  $("#prj-name").value = "";
  $("#prj-folder").value = "";
  $("#prj-url").value = "";
  $("#prj-note").value = "";
  const sel = $("#prj-category");
  sel.innerHTML = STATE.data.categories.map(c => `<option value="${c.id}" ${c.id === categoryId ? "selected" : ""}>${c.icon} ${c.name}</option>`).join("");
  $("#project-modal").classList.remove("hidden");
  $("#prj-name").focus();
}

// ===== 검색 / 사이드 패널 / 토큰 =====
function setupSearch() {
  const input = $("#search-input");
  input.addEventListener("input", () => {
    const q = input.value.trim().toLowerCase();
    $$(".card").forEach((card) => {
      const match = !q || card.dataset.searchKey.includes(q);
      card.style.display = match ? "" : "none";
    });
    $$(".section").forEach((sec) => {
      if (sec.classList.contains("bookmarks-section")) return;
      const visible = sec.querySelectorAll('.card:not([style*="display: none"])').length;
      sec.style.display = visible || !q ? "" : "none";
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "/" && document.activeElement.tagName !== "INPUT") {
      e.preventDefault(); input.focus();
    } else if (e.key === "Escape" && document.activeElement === input) {
      input.value = ""; input.dispatchEvent(new Event("input")); input.blur();
    }
  });
}

function setupSidePanels() {
  $("#logs-toggle").addEventListener("click", async () => {
    $("#links-panel").classList.add("hidden");
    const panel = $("#logs-panel");
    panel.classList.toggle("hidden");
    if (!panel.classList.contains("hidden")) await loadLogs();
  });
  $("#links-toggle").addEventListener("click", () => {
    $("#logs-panel").classList.add("hidden");
    const panel = $("#links-panel");
    panel.classList.toggle("hidden");
    renderLinks();
  });
}

async function loadLogs() {
  const el = $("#logs-content");
  if (!STATE.connected) { el.textContent = "헬퍼가 꺼져 있어."; return; }
  try {
    const j = await api("/api/logs/today");
    el.innerHTML = `<pre>${j.content || "(오늘 작업 기록 없음)"}</pre>`;
  } catch (e) { el.textContent = "실패: " + e.message; }
}

function renderLinks() {
  const el = $("#links-content");
  const items = STATE.data.links || [];
  if (!items.length) { el.innerHTML = `<div class="empty">링크 없음</div>`; return; }
  el.innerHTML = items.map((l) => `
    <a class="link-item" href="${l.url}" target="_blank" rel="noopener">
      <span class="icon">${l.icon || "🔗"}</span>
      <span class="name">${l.name}</span>
    </a>
  `).join("");
}

function setupTokenModal() {
  $("#token-save").addEventListener("click", async () => {
    const tokenVal = $("#token-input").value.trim();
    const urlVal = $("#helper-url-input").value.trim();
    if (urlVal && urlVal !== STATE.helperBase) {
      STATE.helperBase = urlVal.replace(/\/$/, "");
      localStorage.setItem("mintspace_helper", STATE.helperBase);
    }
    if (tokenVal) {
      STATE.token = tokenVal;
      localStorage.setItem("mintspace_token", tokenVal);
    }
    if (!tokenVal && !urlVal) return;
    hideTokenModal();
    await boot(true);
  });
  $("#token-cancel").addEventListener("click", hideTokenModal);
  $("#settings-btn").addEventListener("click", () => {
    $("#helper-url-input").value = STATE.helperBase || "";
    $("#token-input").value = STATE.token || "";
    showTokenModal();
  });
  $("#banner-retry").addEventListener("click", () => boot(true));
}

// ===== 부팅 =====
async function loadProjects() {
  STATE.data = await api("/api/projects");
  renderSidebar();
  renderCategories();
}

async function boot(retry = false) {
  setHelperStatus(false, "확인 중...");
  const alive = await checkHelper();
  if (!alive) {
    setHelperStatus(false, "헬퍼 꺼짐");
    return;
  }
  setHelperStatus(true, "연결됨");
  const ok = await ensureToken();
  if (!ok) { setHelperStatus(true, "토큰 필요"); return; }
  try {
    await loadProjects();
    await loadBookmarks();
  } catch (e) {
    toast("로딩 실패: " + e.message, "err");
    setHelperStatus(false, "인증 실패");
    showTokenModal();
  }
}

// ===== 드래그 앤 드롭 (카드 순서 변경) =====
function setupDragAndDrop() {
  let dragging = null;

  document.addEventListener("dragstart", (e) => {
    const card = e.target.closest(".card[data-pid]");
    if (!card) return;
    dragging = card;
    card.classList.add("dragging");
    const grid = card.closest(".grid");
    if (grid) grid.classList.add("drag-active");
    e.dataTransfer.effectAllowed = "move";
    try { e.dataTransfer.setData("text/plain", card.dataset.pid); } catch {}
  });

  document.addEventListener("dragend", () => {
    if (dragging) dragging.classList.remove("dragging");
    $$(".grid.drag-active").forEach(g => g.classList.remove("drag-active"));
    dragging = null;
  });

  document.addEventListener("dragover", (e) => {
    if (!dragging) return;
    const target = e.target.closest(".card[data-pid]");
    if (!target || target === dragging) return;
    // 같은 카테고리 내에서만
    if (dragging.dataset.cat !== target.dataset.cat) return;
    e.preventDefault();
    const rect = target.getBoundingClientRect();
    const before = e.clientY < rect.top + rect.height / 2;
    const parent = target.parentNode;
    if (before) parent.insertBefore(dragging, target);
    else parent.insertBefore(dragging, target.nextSibling);
  });

  document.addEventListener("drop", async (e) => {
    if (!dragging) return;
    e.preventDefault();
    // 전체 카드 순서 수집
    const newOrder = [];
    $$(".section .card[data-pid]").forEach(c => newOrder.push(c.dataset.pid));
    try {
      await api("/api/projects-order", {
        method: "POST",
        body: JSON.stringify({ ids: newOrder }),
      });
      // 로컬 STATE도 갱신 (재렌더 안 함 - 깜빡임 방지)
      const idMap = {};
      STATE.data.projects.forEach(p => idMap[p.id] = p);
      STATE.data.projects = newOrder.map(id => idMap[id]).filter(Boolean);
      toast("순서 저장됨");
    } catch (err) {
      toast("순서 저장 실패: " + err.message, "err");
    }
  });
}

document.addEventListener("DOMContentLoaded", () => {
  setupSearch();
  setupSidePanels();
  setupTokenModal();
  setupBookmarkInput();
  setupCategoryModal();
  setupProjectModal();
  setupDragAndDrop();
  boot();
});
