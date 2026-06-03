// 민티스페이스 v0.2 — 좌측 사이드바 + 책갈피 + 카테고리/프로젝트 추가

// 즐겨찾기 전용 가상 카테고리 ID. 이 카테고리의 bookmark/rowbreak 는
// 실제 카테고리 목록에 없으므로 메인 영역엔 안 뜨고 즐겨찾기 섹션에만 렌더된다.
// (카테고리 무관 "자주 쓰는 링크" 모음 + 줄바꿈 지원)
const FAV_CAT = "__fav__";

const HELPER_DEFAULT = ["localhost", "127.0.0.1"].includes(location.hostname)
  ? `${location.protocol}//${location.hostname}:5500`
  : `http://localhost:5500`;
const STATE = {
  helperBase: localStorage.getItem("mintspace_helper") || HELPER_DEFAULT,
  token: localStorage.getItem("mintspace_token") || "",
  data: { categories: [], projects: [], links: [] },
  bookmarks: [],
  connected: false,
  editingCatId: null,  // 카테고리 편집 모달용
  editMode: false,     // 편집 모드 (카드 삭제용, ESC로 해제)
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

  // 즐겨찾기 전용 항목(__fav__)은 별도 카운터(⭐)로 세므로 여기선 제외
  $("#nav-bookmark-count").textContent =
    STATE.bookmarks.filter(b => b.type !== "rowbreak" && b.category !== FAV_CAT).length || "";
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
  const bmByCat = {};
  for (const b of STATE.bookmarks) (bmByCat[b.category] ||= []).push(b);

  for (const cat of STATE.data.categories) {
    const list = byCat[cat.id] || [];
    const bmList = bmByCat[cat.id] || [];
    const section = document.createElement("section");
    section.className = "section";
    section.id = `cat-${cat.id}`;
    Object.entries(categoryStyle(cat)).forEach(([k, v]) => section.style.setProperty(k, v));

    const realBmCount = bmList.filter(b => b.type !== "rowbreak").length;
    const sub = `${list.length}개` + (realBmCount ? ` · 바로가기 ${realBmCount}` : "");
    section.innerHTML = `
      <div class="section-header">
        <h2>
          <span class="section-icon">${cat.icon || ""}</span>
          ${cat.name}
        </h2>
        <span class="section-sub">${sub}</span>
        <button class="section-action" data-edit-cat="${cat.id}" title="카테고리 수정">✏</button>
        <button class="section-action" data-add-bm="${cat.id}" title="이 카테고리에 폴더 / 파일 / 링크 추가">+ 바로가기</button>
        <button class="section-action" data-add-rowbreak="${cat.id}" title="미니카드를 줄로 나누기 (줄바꿈 라인 추가, 드래그로 위치 이동)">+ 줄바꿈</button>
        <button class="section-action" data-add-prj="${cat.id}">+ 프로젝트</button>
        ${list.length + bmList.length === 0 ? `<button class="section-action" data-del-cat="${cat.id}" title="빈 카테고리 삭제">✕</button>` : ""}
      </div>
      <div class="grid" data-grid-cat="${cat.id}"></div>
      <div class="shortcuts" data-sc-cat="${cat.id}"></div>
    `;
    const grid = section.querySelector(".grid");
    if (list.length === 0 && bmList.length === 0) {
      grid.innerHTML = `<div class="empty" data-empty-cat="${cat.id}">비어있음 · [+ 프로젝트] 추가 or 다른 카테고리 카드 끌어다 놓기</div>`;
    } else {
      list.forEach(p => grid.appendChild(renderCard(p, cat)));
    }
    const sc = section.querySelector(".shortcuts");
    bmList.forEach(b => sc.appendChild(
      b.type === "rowbreak" ? renderRowBreak(b, cat) : renderChip(b, cat)
    ));
    area.appendChild(section);
  }
}

function renderCard(p, cat) {
  const card = document.createElement("div");
  card.className = "card"
    + (p.exists === false ? " missing" : "")
    + (p.starred ? " starred" : "");
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
      <button class="card-star" data-action="star" title="${p.starred ? '별표 해제' : '별표 (즐겨찾기)'}">${p.starred ? '★' : '☆'}</button>
      <button class="card-edit-btn" data-action="edit" title="이름 변경">✏</button>
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
    if (action === "star") {
      const next = !p.starred;
      try {
        await api(`/api/projects-meta/${p.id}`, { method: "PATCH", body: JSON.stringify({ starred: next }) });
        p.starred = next;
        // 같은 pid 의 카드(메인) + 즐겨찾기 chip 모두 갱신
        $$(`.card[data-pid="${p.id}"], .chip[data-pid="${p.id}"]`).forEach(c => {
          c.classList.toggle("starred", next);
          const s = c.querySelector(".card-star, .chip-star");
          if (s) { s.textContent = next ? "★" : "☆"; s.title = next ? "별표 해제" : "별표 (즐겨찾기)"; }
        });
        renderFavorites();
        loadStarSuggestions();
        toast(next ? `⭐ ${p.name} 즐겨찾기` : `☆ ${p.name} 해제`);
      } catch (err) { toast("실패: " + err.message, "err"); }
      return;
    }
    if (action === "delete") {
      if (!confirm(`프로젝트 "${p.name}" 삭제? (폴더는 그대로)`)) return;
      try {
        await api(`/api/projects-meta/${p.id}`, { method: "DELETE" });
        toast("삭제됨");
        await loadProjects();
      } catch (err) { toast("실패: " + err.message, "err"); }
      return;
    }
    if (action === "edit") {
      openRenameModal("project", p.id, p.name, p.category, p.folder);
      return;
    }
    if (STATE.editMode) return;  // 편집 모드에선 그 외 액션 비활성 (실수 방지)
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

// ===== 바로가기 (미니 카드) - 폴더 / 파일 / 링크 =====
const CHIP_ICONS = { folder: "📁", file: "📄", link: "🔗" };

function renderChip(b, cat) {
  const type = b.type || "folder";
  const icon = CHIP_ICONS[type] || "📁";
  const chip = document.createElement("div");
  chip.className = "chip chip-" + type
    + (b.exists === false ? " missing" : "")
    + (b.starred ? " starred" : "");
  chip.dataset.searchKey = `${b.name} ${b.folder} ${b.note || ""}`.toLowerCase();
  chip.dataset.bid = b.id;
  chip.dataset.cat = b.category;
  chip.title = b.folder + (b.exists === false ? "  (경로 없음)" : "");
  chip.draggable = true;
  Object.entries(categoryStyle(cat)).forEach(([k, v]) => chip.style.setProperty(k, v));
  chip.innerHTML = `
    <button class="chip-edit" data-bm-edit="${b.id}" title="이름 변경">✏</button>
    <button class="chip-star" data-bm-star="${b.id}" title="${b.starred ? '별표 해제' : '별표 (즐겨찾기)'}">${b.starred ? '★' : '☆'}</button>
    <div class="chip-name"><span class="chip-icon">${icon}</span>${b.name}</div>
    <div class="chip-path">${b.folder}</div>
    <button class="chip-del" data-bm-del="${b.id}" title="바로가기 제거">×</button>
  `;
  chip.addEventListener("click", async (e) => {
    // 이름 변경 (편집 모드와 무관)
    const editBtn = e.target.closest("[data-bm-edit]");
    if (editBtn) {
      e.stopPropagation();
      openRenameModal("bookmark", b.id, b.name, b.category, b.folder);
      return;
    }
    // 별표 토글 (편집 모드와 무관)
    const starBtn = e.target.closest("[data-bm-star]");
    if (starBtn) {
      e.stopPropagation();
      const next = !b.starred;
      try {
        await api(`/api/bookmarks/${b.id}`, { method: "PATCH", body: JSON.stringify({ starred: next }) });
        b.starred = next;
        // 같은 bid 의 모든 칩(카테고리 섹션 + 즐겨찾기 섹션)을 부분 갱신
        $$(`.chip[data-bid="${b.id}"]`).forEach(c => {
          c.classList.toggle("starred", next);
          const s = c.querySelector(".chip-star");
          if (s) { s.textContent = next ? "★" : "☆"; s.title = next ? "별표 해제" : "별표 (즐겨찾기)"; }
        });
        renderFavorites();
        toast(next ? `⭐ ${b.name} 즐겨찾기` : `☆ ${b.name} 즐겨찾기 해제`);
      } catch (err) { toast("실패: " + err.message, "err"); }
      return;
    }

    const delBtn = e.target.closest("[data-bm-del]");
    if (delBtn) {
      e.stopPropagation();
      try {
        await api(`/api/bookmarks/${b.id}`, { method: "DELETE" });
        toast("바로가기 제거됨");
        await loadProjects();
      } catch (err) { toast("실패: " + err.message, "err"); }
      return;
    }
    if (STATE.editMode) return;  // 편집 모드에선 본문 클릭 무시 (X만 활성)

    // 링크는 브라우저 새 탭으로 (헬퍼 불필요)
    if (type === "link") {
      window.open(b.folder, "_blank", "noopener");
      toast(`🔗 ${b.name} 열림`);
      return;
    }
    // 폴더 / 파일은 로컬 헬퍼가 os.startfile 로 처리
    if (!STATE.connected) return toast("헬퍼가 꺼져 있어", "err");
    try {
      await api("/api/open-folder", { method: "POST", body: JSON.stringify({ folder: b.folder, project_id: "bm-" + b.id }) });
      const verb = type === "file" ? "📄" : "📂";
      toast(`${verb} ${b.name} 열림`);
    } catch (err) { toast("실패: " + err.message, "err"); }
  });
  return chip;
}

// 줄바꿈 라인 (미니카드를 줄 단위로 묶기) — grid 전체 폭을 차지해 뒤 카드를 다음 줄로 밀어냄
function renderRowBreak(b, cat) {
  const el = document.createElement("div");
  el.className = "rowbreak";
  el.dataset.bid = b.id;
  el.dataset.cat = b.category;
  el.dataset.searchKey = "";  // 검색 시 같이 숨기기 위해 빈 키
  el.draggable = true;
  el.title = "줄바꿈 라인 · 드래그로 위치 이동";
  Object.entries(categoryStyle(cat)).forEach(([k, v]) => el.style.setProperty(k, v));
  el.innerHTML = `
    <span class="rowbreak-label">⸻ 줄바꿈 ⸻</span>
    <button class="rowbreak-del" data-bm-del="${b.id}" title="줄바꿈 제거">×</button>
  `;
  el.addEventListener("click", async (e) => {
    const delBtn = e.target.closest("[data-bm-del]");
    if (!delBtn) return;
    e.stopPropagation();
    try {
      await api(`/api/bookmarks/${b.id}`, { method: "DELETE" });
      toast("줄바꿈 제거됨");
      await loadProjects();
    } catch (err) { toast("실패: " + err.message, "err"); }
  });
  return el;
}

// 프로젝트를 즐겨찾기 섹션용 컴팩트 칩으로 (큰 카드 아닌 미니카드 형태)
function renderProjectChip(p, cat) {
  const chip = document.createElement("div");
  chip.className = "chip chip-project starred"
    + (p.exists === false ? " missing" : "");
  chip.dataset.searchKey = `${p.name} ${p.folder} ${p.note || ""}`.toLowerCase();
  chip.dataset.pid = p.id;
  chip.dataset.cat = p.category;
  chip.title = p.folder + (p.exists === false ? "  (폴더 없음)" : "");
  Object.entries(categoryStyle(cat)).forEach(([k, v]) => chip.style.setProperty(k, v));
  chip.innerHTML = `
    <button class="chip-star" data-pj-star="${p.id}" title="별표 해제">★</button>
    <div class="chip-name"><span class="chip-icon">📦</span>${p.name}</div>
    <div class="chip-path">${p.folder}</div>
  `;
  chip.addEventListener("click", async (e) => {
    const starBtn = e.target.closest("[data-pj-star]");
    if (starBtn) {
      e.stopPropagation();
      try {
        await api(`/api/projects-meta/${p.id}`, { method: "PATCH", body: JSON.stringify({ starred: false }) });
        p.starred = false;
        // 같은 pid 의 메인 카드 갱신
        $$(`.card[data-pid="${p.id}"]`).forEach(c => {
          c.classList.remove("starred");
          const s = c.querySelector(".card-star");
          if (s) { s.textContent = "☆"; s.title = "별표 (즐겨찾기)"; }
        });
        renderFavorites();
        loadStarSuggestions();
        toast(`☆ ${p.name} 해제`);
      } catch (err) { toast("실패: " + err.message, "err"); }
      return;
    }
    if (STATE.editMode) return;
    if (!STATE.connected) return toast("헬퍼가 꺼져 있어", "err");
    try {
      await api("/api/open-folder", { method: "POST", body: JSON.stringify({ folder: p.folder, project_id: p.id }) });
      toast(`📂 ${p.name} 열림`);
    } catch (err) { toast("실패: " + err.message, "err"); }
  });
  return chip;
}

// 즐겨찾기 섹션: ① 즐겨찾기 전용 항목(__fav__, 줄바꿈 포함, 순서 유지)
//              ② 별표된 프로젝트(📦)  ③ 다른 카테고리에서 별표된 미니카드
// 카테고리 무관 "자주 쓰는 링크" 를 직접 추가하거나 다른 카드를 끌어다 모을 수 있다.
const FAV_CAT_META = { id: FAV_CAT, color: "#f59e0b", icon: "⭐", name: "즐겨찾기" };

function renderFavorites() {
  const sec = $("#favorites");
  const grid = $("#favorites-grid");
  if (!sec || !grid) return;
  // ① 즐겨찾기 전용 항목 (글로벌 순서 유지 · 줄바꿈 라인 포함)
  const favNative = STATE.bookmarks.filter(b => b.category === FAV_CAT);
  // ②③ 별표된 항목 (전용 항목과 겹치지 않게 __fav__ 는 제외해 중복 방지)
  const starredBm = STATE.bookmarks.filter(b => b.starred && b.category !== FAV_CAT);
  const starredPj = (STATE.data.projects || []).filter(p => p.starred);

  const realFavCount = favNative.filter(b => b.type !== "rowbreak").length;
  const total = realFavCount + starredBm.length + starredPj.length;
  const navCount = $("#nav-fav-count");
  if (navCount) navCount.textContent = total || "";

  // 전용 항목이 하나라도 있으면, 비어 보여도 [+ 바로가기] 버튼은 계속 쓸 수 있게
  // 섹션은 띄워둔다. (전용 항목 0 + 별표 0 일 때만 숨김)
  if (total === 0 && favNative.length === 0) {
    sec.classList.add("hidden");
    grid.innerHTML = "";
    return;
  }
  sec.classList.remove("hidden");
  grid.innerHTML = "";

  // ① 즐겨찾기 전용 (줄바꿈 포함, 순서 유지)
  for (const b of favNative) {
    grid.appendChild(b.type === "rowbreak" ? renderRowBreak(b, FAV_CAT_META) : renderChip(b, FAV_CAT_META));
  }
  // ② 별표된 프로젝트
  for (const p of starredPj) {
    const cat = STATE.data.categories.find(c => c.id === p.category)
      || { id: p.category, color: "#888", icon: "📁", name: p.category || "기타" };
    grid.appendChild(renderProjectChip(p, cat));
  }
  // ③ 다른 카테고리에서 별표된 미니카드
  for (const b of starredBm) {
    const cat = STATE.data.categories.find(c => c.id === b.category)
      || { id: b.category, color: "#888", icon: "📁", name: b.category || "기타" };
    grid.appendChild(renderChip(b, cat));
  }
}

function fillBookmarkCatSelect(selectedId) {
  const sel = $("#bm-category");
  if (!sel) return;
  // 맨 위에 "⭐ 즐겨찾기" 가상 카테고리 → 어떤 추가창에서든 즐겨찾기로 바로 보낼 수 있게
  sel.innerHTML =
    `<option value="${FAV_CAT}">⭐ 즐겨찾기</option>`
    + STATE.data.categories
      .map(c => `<option value="${c.id}">${c.icon || "📁"} ${c.name}</option>`)
      .join("");
  if (selectedId) sel.value = selectedId;
}

function openBookmarkModal(catId) {
  $("#bm-folder").value = "";
  $("#bm-name").value = "";
  fillBookmarkCatSelect(catId);
  $("#bookmark-modal").classList.remove("hidden");
  $("#bm-folder").focus();
}

function setupBookmarkModal() {
  // 각 카테고리 [+ 폴더] 버튼 위임
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-add-bm]");
    if (btn) openBookmarkModal(btn.dataset.addBm);
  });

  // [+ 줄바꿈] 버튼 위임 — 해당 카테고리 끝에 줄바꿈 라인 추가
  document.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-add-rowbreak]");
    if (!btn) return;
    try {
      await api("/api/bookmarks-rowbreak", {
        method: "POST",
        body: JSON.stringify({ category: btn.dataset.addRowbreak }),
      });
      toast("➖ 줄바꿈 추가됨 · 드래그로 위치 옮겨");
      await loadProjects();
    } catch (err) { toast("실패: " + err.message, "err"); }
  });

  async function save() {
    const folder = $("#bm-folder").value.trim().replace(/^["']|["']$/g, "");
    if (!folder) return toast("폴더 경로를 입력해", "err");
    try {
      await api("/api/bookmarks", {
        method: "POST",
        body: JSON.stringify({
          folder,
          name: $("#bm-name").value.trim() || null,
          category: $("#bm-category").value || "tool",
        }),
      });
      $("#bookmark-modal").classList.add("hidden");
      toast("📁 폴더 바로가기 추가됨");
      await loadProjects();
    } catch (err) { toast("실패: " + err.message, "err"); }
  }
  $("#bm-save").addEventListener("click", save);
  $("#bm-folder").addEventListener("keydown", e => { if (e.key === "Enter") save(); });
  $("#bm-name").addEventListener("keydown", e => { if (e.key === "Enter") save(); });

  // 바탕화면 다시 스캔 → 새 폴더만 가져오기
  $("#rescan-btn").addEventListener("click", async () => {
    if (!STATE.connected) return toast("헬퍼가 꺼져 있어", "err");
    const b = $("#rescan-btn");
    b.disabled = true;
    const orig = b.textContent;
    b.textContent = "🖥 스캔 중...";
    try {
      const r = await api("/api/bookmarks-import", { method: "POST" });
      toast(r.added ? `🖥 ${r.added}개 새로 추가됨 (중복 ${r.skipped})` : `새로 추가된 폴더 없음 (중복 ${r.skipped})`);
      await loadProjects();
    } catch (err) { toast("실패: " + err.message, "err"); }
    finally { b.disabled = false; b.textContent = orig; }
  });
}

// ===== 카테고리 추가/편집 (한 모달 재활용) =====
function setupCategoryModal() {
  // 추가 모드
  $("#add-category-btn").addEventListener("click", () => {
    STATE.editingCatId = null;
    $("#category-modal h3").textContent = "새 카테고리";
    $("#cat-name").value = "";
    $("#cat-icon").value = "📁";
    $("#cat-color").value = "#10b981";
    $("#category-modal").classList.remove("hidden");
    $("#cat-name").focus();
  });

  // 편집 모드 (✏ 버튼 위임)
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-edit-cat]");
    if (!btn) return;
    const cat = STATE.data.categories.find(c => c.id === btn.dataset.editCat);
    if (!cat) return;
    STATE.editingCatId = cat.id;
    $("#category-modal h3").textContent = `카테고리 수정: ${cat.name}`;
    $("#cat-name").value = cat.name;
    $("#cat-icon").value = cat.icon || "📁";
    $("#cat-color").value = cat.color || "#10b981";
    $("#category-modal").classList.remove("hidden");
    $("#cat-name").focus();
    $("#cat-name").select();
  });

  $("#cat-save").addEventListener("click", async () => {
    const name = $("#cat-name").value.trim();
    if (!name) return toast("이름을 입력해", "err");
    const payload = {
      name,
      icon: $("#cat-icon").value.trim() || "📁",
      color: $("#cat-color").value,
    };
    try {
      if (STATE.editingCatId) {
        await api(`/api/categories/${STATE.editingCatId}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        toast(`✏ "${name}" 수정됨`);
      } else {
        await api("/api/categories", {
          method: "POST",
          body: JSON.stringify(payload),
        });
        toast(`✅ 카테고리 "${name}" 추가됨`);
      }
      $("#category-modal").classList.add("hidden");
      STATE.editingCatId = null;
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
    $$(".card, .chip, .rowbreak").forEach((el) => {
      const match = !q || (el.dataset.searchKey || "").includes(q);
      el.style.display = match ? "" : "none";
    });
    $$(".section").forEach((sec) => {
      if (sec.classList.contains("bookmarks-section")) return;
      const visible = sec.querySelectorAll('.card:not([style*="display: none"]), .chip:not([style*="display: none"])').length;
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

// ===== 카드 편집 모달 (이름 + 카테고리 공통) =====
let renameTarget = null;

function fillRenameCatSelect(selectedId, kind) {
  const sel = $("#rn-category");
  if (!sel) return;
  // 미니카드(bookmark)만 즐겨찾기로 이동 가능 (프로젝트는 서버가 실제 카테고리만 허용)
  const favOpt = kind === "bookmark" ? `<option value="${FAV_CAT}">⭐ 즐겨찾기</option>` : "";
  sel.innerHTML = favOpt + STATE.data.categories
    .map(c => `<option value="${c.id}">${c.icon || "📁"} ${c.name}</option>`)
    .join("");
  if (selectedId) sel.value = selectedId;
}

function openRenameModal(kind, id, currentName, currentCategory, currentFolder) {
  renameTarget = { kind, id };
  $("#rn-name").value = currentName || "";
  $("#rn-folder").value = currentFolder || "";
  fillRenameCatSelect(currentCategory, kind);
  $("#rename-modal").classList.remove("hidden");
  // focus / select 는 모달이 보이고 난 뒤
  setTimeout(() => { $("#rn-name").focus(); $("#rn-name").select(); }, 0);
}

function setupRenameModal() {
  async function save() {
    if (!renameTarget) return;
    const next = $("#rn-name").value.trim();
    const newCat = $("#rn-category").value;
    const folder = $("#rn-folder").value.trim().replace(/^["']|["']$/g, "");
    if (!next) return toast("이름이 비어있어", "err");
    if (!folder) return toast("경로가 비어있어", "err");
    const endpoint = renameTarget.kind === "bookmark"
      ? `/api/bookmarks/${renameTarget.id}`
      : `/api/projects-meta/${renameTarget.id}`;
    try {
      await api(endpoint, {
        method: "PATCH",
        body: JSON.stringify({ name: next, category: newCat, folder }),
      });
      $("#rename-modal").classList.add("hidden");
      toast(`✏ "${next}" 저장됨`);
      renameTarget = null;
      await loadProjects();
    } catch (err) { toast("실패: " + err.message, "err"); }
  }
  $("#rn-save").addEventListener("click", save);
  $("#rn-name").addEventListener("keydown", e => { if (e.key === "Enter") save(); });
}

// ===== 자주 여는 폴더 자동 별표 추천 (logs 분석) =====
async function loadStarSuggestions() {
  if (!STATE.connected) return;
  try {
    const r = await api("/api/star-suggestions?days=7&threshold=5");
    STATE.suggestions = r;
    const apply = r.star_recommend.length + r.unstar_recommend.length;
    const btn = $("#suggest-btn");
    if (!btn) return;
    if (apply === 0 && r.project_top.length === 0) {
      btn.classList.add("hidden");
    } else {
      btn.classList.remove("hidden");
      $("#suggest-count").textContent = apply;
    }
  } catch (e) {
    console.error("추천 로딩 실패", e);
  }
}

function openSuggestModal() {
  const data = STATE.suggestions;
  if (!data) return;
  $("#ss-days").textContent = data.days;
  $("#ss-add-count").textContent = data.star_recommend.length;
  $("#ss-remove-count").textContent = data.unstar_recommend.length;

  function renderItems(list, action, container) {
    if (!list.length) {
      container.innerHTML = '<div class="ss-empty">없음</div>';
      return;
    }
    container.innerHTML = list.map(it => {
      const cat = STATE.data.categories.find(c => c.id === it.category);
      const catLabel = cat ? `${cat.icon || ""} ${cat.name}` : (it.category || "");
      const icon = it.kind === "project" ? "📦" : (CHIP_ICONS[it.type] || "📁");
      const meta = it.count ? `${catLabel} · ${it.count}회` : catLabel;
      const cb = action
        ? `<input type="checkbox" data-ss-action="${action}" data-ss-id="${it.id}" data-ss-kind="${it.kind || 'bookmark'}" checked />`
        : '<span class="ss-bullet">·</span>';
      return `
        <label class="ss-item">
          ${cb}
          <span class="ss-icon">${icon}</span>
          <span class="ss-name">${it.name}</span>
          <span class="ss-meta">${meta}</span>
        </label>`;
    }).join("");
  }
  renderItems(data.star_recommend, "add", $("#ss-add-list"));
  renderItems(data.unstar_recommend, "remove", $("#ss-remove-list"));
  renderItems(data.project_top, null, $("#ss-projects-list"));

  $("#star-suggest-modal").classList.remove("hidden");
}

function setupStarSuggest() {
  const btn = $("#suggest-btn");
  if (btn) btn.addEventListener("click", openSuggestModal);

  const apply = $("#ss-apply");
  if (apply) apply.addEventListener("click", async () => {
    const checks = $$(".ss-item input[data-ss-action]:checked");
    if (!checks.length) {
      $("#star-suggest-modal").classList.add("hidden");
      return;
    }
    let added = 0, removed = 0, failed = 0;
    for (const cb of checks) {
      const action = cb.dataset.ssAction;
      const id = cb.dataset.ssId;
      const kind = cb.dataset.ssKind || "bookmark";
      const starred = action === "add";
      const endpoint = kind === "project" ? `/api/projects-meta/${id}` : `/api/bookmarks/${id}`;
      try {
        await api(endpoint, { method: "PATCH", body: JSON.stringify({ starred }) });
        if (starred) added++; else removed++;
      } catch { failed++; }
    }
    $("#star-suggest-modal").classList.add("hidden");
    let msg = `✓ 별표 ${added}개 추가 · ${removed}개 해제`;
    if (failed) msg += ` · ${failed}개 실패`;
    toast(msg);
    await loadProjects();
    await loadStarSuggestions();
  });
}

// ===== 편집 모드 (카드 삭제 안전화) =====
function setupEditMode() {
  const btn = $("#edit-toggle");
  function toggle(force) {
    const next = (typeof force === "boolean") ? force : !STATE.editMode;
    STATE.editMode = next;
    document.body.classList.toggle("edit-mode", next);
    btn.classList.toggle("active", next);
    btn.innerHTML = next
      ? `<span class="edit-icon">✓</span><span class="edit-label">편집 끝</span>`
      : `<span class="edit-icon">✎</span><span class="edit-label">편집</span>`;
  }
  btn.addEventListener("click", () => toggle());
  // ESC로 편집 모드 빠져나오기 (검색 input 활성 아닐 때만)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && STATE.editMode && document.activeElement.tagName !== "INPUT") {
      toggle(false);
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
  const [proj, bm] = await Promise.all([
    api("/api/projects"),
    api("/api/bookmarks"),
  ]);
  STATE.data = proj;
  STATE.bookmarks = bm.bookmarks || [];
  renderSidebar();
  fillBookmarkCatSelect();
  renderCategories();
  renderFavorites();
  loadStarSuggestions();  // 비동기, 별도 fetch (UI 막지 않음)
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
  } catch (e) {
    toast("로딩 실패: " + e.message, "err");
    setHelperStatus(false, "인증 실패");
    showTokenModal();
  }
}

// ===== 드래그 앤 드롭 (카드 순서 변경 + 카테고리 간 이동) =====
function setupDragAndDrop() {
  let dragging = null;
  let originalCat = null;  // 드래그 시작 시점 카테고리 (변경 감지용)
  let saved = false;       // drop에서 저장됐는지 (dragend fallback 판단용)

  // 현재 DOM 순서 + 카테고리 변경을 서버에 저장.
  // card/fromCat을 인자로 받아 drop의 async 진행 중 dragend가 상태를
  // 비워도 영향받지 않게 한다.
  async function persistOrder(card, fromCat) {
    const movedToOtherCat = card.dataset.cat !== fromCat;
    const pid = card.dataset.pid;
    const newCat = card.dataset.cat;
    try {
      // 카테고리가 바뀌었으면 먼저 PATCH
      if (movedToOtherCat) {
        await api(`/api/projects-meta/${pid}`, {
          method: "PATCH",
          body: JSON.stringify({ category: newCat }),
        });
        // STATE도 갱신
        const p = STATE.data.projects.find(p => p.id === pid);
        if (p) p.category = newCat;
      }

      // 전체 순서 저장 (카테고리별 grid 순서 = 전역 projects 순서)
      const newOrder = [];
      $$(".section .card[data-pid]").forEach(c => newOrder.push(c.dataset.pid));
      await api("/api/projects-order", {
        method: "POST",
        body: JSON.stringify({ ids: newOrder }),
      });
      const idMap = {};
      STATE.data.projects.forEach(p => idMap[p.id] = p);
      STATE.data.projects = newOrder.map(id => idMap[id]).filter(Boolean);

      if (movedToOtherCat) {
        toast(`✅ "${card.querySelector('.card-title')?.textContent.trim().split(' ')[0]}" 이동됨`);
        // 빈 grid 카운트 / 헤더 등 다시 그려야 정확
        await loadProjects();
      } else {
        toast("순서 저장됨");
      }
    } catch (err) {
      toast("저장 실패: " + err.message, "err");
      await loadProjects();  // 실패 시 서버 상태로 복구
    }
  }

  document.addEventListener("dragstart", (e) => {
    const card = e.target.closest(".card[data-pid]");
    if (!card) return;
    dragging = card;
    originalCat = card.dataset.cat;
    saved = false;
    card.classList.add("dragging");
    $$(".grid").forEach(g => g.classList.add("drag-active"));
    e.dataTransfer.effectAllowed = "move";
    try { e.dataTransfer.setData("text/plain", card.dataset.pid); } catch {}
  });

  document.addEventListener("dragend", () => {
    const card = dragging;
    const fromCat = originalCat;
    if (card) card.classList.remove("dragging");
    $$(".grid.drag-active").forEach(g => g.classList.remove("drag-active"));
    $$(".grid.drag-over").forEach(g => g.classList.remove("drag-over"));
    dragging = null;
    originalCat = null;
    // drop이 발생하지 않은 채 드래그가 끝난 경우(카드 사이 간격·빈 영역 등)
    // 화면만 바뀌고 저장이 누락되지 않도록 여기서 저장한다.
    if (card && !saved) persistOrder(card, fromCat);
  });

  document.addEventListener("dragover", (e) => {
    if (!dragging) return;
    // 드래그 중에는 항상 drop을 허용해야 어디에 놓아도 drop 이벤트가 발생한다.
    // (안 그러면 dragover로 화면만 바뀌고 저장이 누락됨)
    e.preventDefault();

    // 1. 카드 위로 드래그 (위치 결정)
    const targetCard = e.target.closest(".card[data-pid]");
    if (targetCard && targetCard !== dragging) {
      const newGrid = targetCard.closest(".grid");
      const newCat = newGrid?.dataset.gridCat;
      if (newCat && newCat !== dragging.dataset.cat) {
        dragging.dataset.cat = newCat;  // 카테고리 시각 갱신
      }
      const rect = targetCard.getBoundingClientRect();
      const before = e.clientY < rect.top + rect.height / 2;
      const parent = targetCard.parentNode;
      if (before) parent.insertBefore(dragging, targetCard);
      else parent.insertBefore(dragging, targetCard.nextSibling);
      return;
    }

    // 2. 빈 grid 위로 드래그 (그 카테고리로 이동)
    const targetGrid = e.target.closest(".grid[data-grid-cat]");
    if (targetGrid && !targetGrid.contains(dragging)) {
      const newCat = targetGrid.dataset.gridCat;
      const emptyMsg = targetGrid.querySelector(".empty");
      if (emptyMsg) emptyMsg.remove();
      dragging.dataset.cat = newCat;
      targetGrid.appendChild(dragging);
    }
  });

  document.addEventListener("drop", (e) => {
    if (!dragging) return;
    e.preventDefault();
    saved = true;  // dragend fallback 방지
    persistOrder(dragging, originalCat);
  });
}

// ===== 칩(폴더 바로가기) 드래그 → 순서 변경 + 카테고리 이동 =====
// 카드 드래그(setupDragAndDrop)와는 각자 클로저의 dragging 상태로 배타 분기된다.
function setupChipDrag() {
  let dragging = null;
  let originalCat = null;
  let saved = false;

  // 현재 DOM 순서 + 카테고리 변경을 서버에 저장.
  async function persistChipOrder(chip, fromCat) {
    const movedCat = chip.dataset.cat !== fromCat;
    const bid = chip.dataset.bid;
    const newCat = chip.dataset.cat;
    try {
      if (movedCat) {
        await api(`/api/bookmarks/${bid}`, {
          method: "PATCH",
          body: JSON.stringify({ category: newCat }),
        });
        const b = STATE.bookmarks.find(x => x.id === bid);
        if (b) b.category = newCat;
      }
      // 전체 순서 저장 (DOM 순서 = 전역 bookmarks 순서). 줄바꿈 라인(.rowbreak)도
      // 위치를 차지하므로 함께 수집. 즐겨찾기 섹션(__fav__ 전용 항목)도 포함해
      // 즐겨찾기 안에서의 순서 변경도 저장되게 한다.
      // 별표 항목은 자기 카테고리 + 즐겨찾기 양쪽에 같은 data-bid 로 중복 존재하므로
      // Set 으로 중복 제거 (문서 순서상 즐겨찾기가 먼저라 첫 등장만 채택).
      const newOrder = [];
      const seenBid = new Set();
      $$("#favorites-grid [data-bid], #categories-area .shortcuts [data-bid]").forEach(c => {
        if (!seenBid.has(c.dataset.bid)) { seenBid.add(c.dataset.bid); newOrder.push(c.dataset.bid); }
      });
      await api("/api/bookmarks-order", {
        method: "POST",
        body: JSON.stringify({ ids: newOrder }),
      });
      const map = {};
      STATE.bookmarks.forEach(b => map[b.id] = b);
      STATE.bookmarks = newOrder.map(id => map[id]).filter(Boolean);

      if (movedCat) {
        const catName = STATE.data.categories.find(c => c.id === newCat)?.name || newCat;
        const label = chip.querySelector('.chip-name')?.textContent.trim() || "줄바꿈";
        toast(`📁 "${label}" → ${catName}`);
        await loadProjects();  // 헤더 카운트 갱신
      } else {
        toast("순서 저장됨");
      }
    } catch (err) {
      toast("저장 실패: " + err.message, "err");
      await loadProjects();
    }
  }

  document.addEventListener("dragstart", (e) => {
    const chip = e.target.closest(".chip[data-bid], .rowbreak[data-bid]");
    if (!chip) return;
    dragging = chip;
    originalCat = chip.dataset.cat;
    saved = false;
    chip.classList.add("dragging");
    $$(".shortcuts").forEach(s => s.classList.add("drag-active"));
    try { e.dataTransfer.effectAllowed = "move"; } catch {}
  });

  document.addEventListener("dragend", () => {
    const chip = dragging;
    const fromCat = originalCat;
    if (chip) chip.classList.remove("dragging");
    $$(".shortcuts.drag-active").forEach(s => s.classList.remove("drag-active"));
    dragging = null;
    originalCat = null;
    if (chip && !saved) persistChipOrder(chip, fromCat);
  });

  document.addEventListener("dragover", (e) => {
    if (!dragging) return;
    e.preventDefault();

    // 1. 다른 칩(또는 줄바꿈) 위로 드래그 (위치 결정)
    const targetChip = e.target.closest(".chip[data-bid], .rowbreak[data-bid]");
    if (targetChip && targetChip !== dragging) {
      const newSc = targetChip.closest(".shortcuts");
      const newCat = newSc?.dataset.scCat;
      if (newCat && newCat !== dragging.dataset.cat) dragging.dataset.cat = newCat;
      const rect = targetChip.getBoundingClientRect();
      // 미니 카드는 그리드라 좌우 위치도 고려
      const before = e.clientY < rect.top + rect.height / 2
        || (Math.abs(e.clientY - (rect.top + rect.height / 2)) < rect.height / 2 && e.clientX < rect.left + rect.width / 2);
      const parent = targetChip.parentNode;
      if (before) parent.insertBefore(dragging, targetChip);
      else parent.insertBefore(dragging, targetChip.nextSibling);
      return;
    }

    // 2. 빈 shortcuts 영역으로 드래그 (그 카테고리로 이동)
    const targetSc = e.target.closest(".shortcuts[data-sc-cat]");
    if (targetSc && !targetSc.contains(dragging)) {
      dragging.dataset.cat = targetSc.dataset.scCat;
      targetSc.appendChild(dragging);
    }
  });

  document.addEventListener("drop", (e) => {
    if (!dragging) return;
    e.preventDefault();
    saved = true;
    persistChipOrder(dragging, originalCat);
  });
}

// ===== 사이드바 카테고리 = 드롭존 (멀리 있는 카테고리로 빠르게 이동) =====
// drop 시 DOM 만 옮기고, 카드/칩 dnd 의 dragend 가 저장을 마무리한다.
function setupSidebarDropZones() {
  const nav = $("#nav-categories");
  if (!nav) return;

  nav.addEventListener("dragover", (e) => {
    const item = e.target.closest(".nav-item[data-cat]");
    if (!item) return;
    if (!document.querySelector(".chip.dragging, .card.dragging")) return;
    e.preventDefault();
    e.stopPropagation();
    item.classList.add("drop-target");
  });

  nav.addEventListener("dragleave", (e) => {
    const item = e.target.closest(".nav-item[data-cat]");
    if (item && !item.contains(e.relatedTarget)) item.classList.remove("drop-target");
  });

  nav.addEventListener("drop", (e) => {
    const item = e.target.closest(".nav-item[data-cat]");
    if (!item) return;
    e.preventDefault();
    e.stopPropagation();
    item.classList.remove("drop-target");

    const newCat = item.dataset.cat;
    const dragChip = document.querySelector(".chip.dragging");
    const dragCard = document.querySelector(".card.dragging");

    if (dragChip) {
      dragChip.dataset.cat = newCat;
      const targetSc = document.querySelector(`.shortcuts[data-sc-cat="${newCat}"]`);
      if (targetSc) targetSc.appendChild(dragChip);
    } else if (dragCard) {
      dragCard.dataset.cat = newCat;
      const targetGrid = document.querySelector(`.grid[data-grid-cat="${newCat}"]`);
      if (targetGrid) {
        const empty = targetGrid.querySelector(".empty");
        if (empty) empty.remove();
        targetGrid.appendChild(dragCard);
      }
    }
    // dragend → persistOrder / persistChipOrder 가 PATCH + 순서 저장 처리
  });
}

// ===== 드래그 중 화면 가장자리에서 자동 스크롤 =====
function setupAutoScroll() {
  const EDGE = 80;        // 가장자리 80px
  const MAX_SPEED = 18;   // px/frame
  let delta = 0;
  let handle = null;
  function tick() {
    if (!delta) { handle = null; return; }
    window.scrollBy(0, delta);
    handle = requestAnimationFrame(tick);
  }
  function start() { if (!handle) handle = requestAnimationFrame(tick); }
  function stop() {
    if (handle) cancelAnimationFrame(handle);
    handle = null;
    delta = 0;
  }
  document.addEventListener("dragover", (e) => {
    if (!document.querySelector(".chip.dragging, .card.dragging, .rowbreak.dragging")) { stop(); return; }
    const y = e.clientY;
    const h = window.innerHeight;
    if (y < EDGE) delta = -MAX_SPEED * (1 - y / EDGE);
    else if (y > h - EDGE) delta = MAX_SPEED * (1 - (h - y) / EDGE);
    else delta = 0;
    if (delta) start(); else stop();
  });
  document.addEventListener("dragend", stop);
  document.addEventListener("drop", stop);
}

document.addEventListener("DOMContentLoaded", () => {
  setupSearch();
  setupEditMode();
  setupSidePanels();
  setupTokenModal();
  setupBookmarkModal();
  setupRenameModal();
  setupStarSuggest();
  setupCategoryModal();
  setupProjectModal();
  setupDragAndDrop();
  setupChipDrag();
  setupSidebarDropZones();
  setupAutoScroll();
  boot();
});
