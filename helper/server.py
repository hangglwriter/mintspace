"""민티스페이스 로컬 헬퍼 (FastAPI).

브라우저 대시보드(로컬 또는 배포)에서 호출하는 API.
- 폴더 탐색기 열기
- Windows Terminal + PowerShell 7 + cldp 실행
- 프로젝트 메타 / 작업 로그 관리
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import secrets
import shutil
import subprocess
import sys
import traceback
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import desktop_scan

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
WEB_DIR = ROOT / "web"
LOG_DIR = DATA_DIR / "logs"
TOKEN_FILE = DATA_DIR / "token.txt"
PROJECTS_FILE = DATA_DIR / "projects.json"
BOOKMARKS_FILE = DATA_DIR / "bookmarks.json"

LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("mintspace")


def get_or_create_token() -> str:
    if TOKEN_FILE.exists():
        token = TOKEN_FILE.read_text(encoding="utf-8").strip()
        if token:
            return token
    token = secrets.token_urlsafe(24)
    TOKEN_FILE.write_text(token, encoding="utf-8")
    return token


def find_pwsh() -> str:
    candidates = [
        r"C:\Program Files\PowerShell\7\pwsh.exe",
        r"C:\Program Files (x86)\PowerShell\7\pwsh.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WindowsApps\pwsh.exe"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    p = shutil.which("pwsh")
    if p:
        return p
    p = shutil.which("powershell")
    if p:
        return p
    return "powershell.exe"


def find_wt() -> Optional[str]:
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), r"Microsoft\WindowsApps\wt.exe"),
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
    p = shutil.which("wt")
    return p


TOKEN = get_or_create_token()
PWSH = find_pwsh()
WT = find_wt()
log.info("PowerShell: %s", PWSH)
log.info("WindowsTerminal: %s", WT or "(없음)")

app = FastAPI(title="민티스페이스 헬퍼", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^(http://(localhost|127\.0\.0\.1)(:\d+)?|https://([a-z0-9-]+\.)?pages\.dev|https://([a-z0-9-]+\.)?vercel\.app|https://([a-z0-9-]+\.)?mintspace\.([a-z0-9-]+\.)*[a-z]+)$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def require_token(x_token: Optional[str]) -> None:
    if x_token != TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


class ProjectRef(BaseModel):
    folder: str
    project_id: Optional[str] = None


class LogEntry(BaseModel):
    project_id: Optional[str] = None
    message: str


class Bookmark(BaseModel):
    folder: str
    name: Optional[str] = None
    note: Optional[str] = None
    category: Optional[str] = None


class CategoryIn(BaseModel):
    id: Optional[str] = None
    name: str
    icon: Optional[str] = None
    color: Optional[str] = None


class ProjectIn(BaseModel):
    id: Optional[str] = None
    name: str
    category: str
    folder: str
    url: Optional[str] = None
    note: Optional[str] = None


class OrderIn(BaseModel):
    ids: list[str]


class CategoryPatch(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    color: Optional[str] = None


class ProjectPatch(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    folder: Optional[str] = None
    url: Optional[str] = None
    note: Optional[str] = None


def load_projects_data() -> dict:
    if not PROJECTS_FILE.exists():
        return {"categories": [], "projects": [], "links": []}
    return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))


def save_projects_data(data: dict) -> None:
    PROJECTS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def slugify(text: str) -> str:
    import re
    s = re.sub(r"[^\w\-]+", "-", text.strip().lower()).strip("-")
    return s or secrets.token_hex(4)


def load_bookmarks() -> list:
    if not BOOKMARKS_FILE.exists():
        return []
    try:
        return json.loads(BOOKMARKS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_bookmarks(items: list) -> None:
    BOOKMARKS_FILE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def append_log(line: str) -> None:
    today = dt.date.today().isoformat()
    log_file = LOG_DIR / f"{today}.md"
    timestamp = dt.datetime.now().strftime("%H:%M")
    with log_file.open("a", encoding="utf-8") as f:
        f.write(f"- {timestamp}  {line}\n")


# ---------- 공개 (인증 X) ----------

@app.get("/api/health")
def health():
    return {"ok": True, "version": "0.2.0", "pwsh": PWSH, "wt": WT}


@app.get("/api/token-bootstrap")
def token_bootstrap(request: Request):
    """로컬 접속에서만 토큰 발급."""
    host = (request.client.host if request.client else "") or ""
    if host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=403, detail="local only")
    return {"token": TOKEN}


# ---------- 인증 필요 ----------

@app.get("/api/projects")
def get_projects(x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    if not PROJECTS_FILE.exists():
        return {"categories": [], "projects": [], "links": []}
    data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    # 각 프로젝트에 폴더 메타 추가
    for p in data.get("projects", []):
        try:
            f = Path(p["folder"])
            p["exists"] = f.exists()
            if p["exists"]:
                stat = f.stat()
                p["last_modified"] = int(stat.st_mtime)
            else:
                p["last_modified"] = None
        except Exception:
            p["exists"] = False
            p["last_modified"] = None
    return data


@app.post("/api/open-folder")
def open_folder(body: ProjectRef, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    folder = Path(body.folder)
    if not folder.exists():
        log.warning("폴더 없음: %s", folder)
        raise HTTPException(status_code=404, detail=f"폴더 없음: {folder}")
    try:
        os.startfile(str(folder))
    except Exception as e:
        log.error("폴더 열기 실패: %s -> %s\n%s", folder, e, traceback.format_exc())
        # fallback
        try:
            subprocess.Popen(["explorer.exe", str(folder)])
        except Exception as e2:
            raise HTTPException(status_code=500, detail=f"폴더 열기 실패: {e2}")
    append_log(f"📂 [{body.project_id or folder.name}] 폴더 열림")
    return {"ok": True, "opened": str(folder)}


@app.post("/api/launch-terminal")
def launch_terminal(body: ProjectRef, x_token: Optional[str] = Header(default=None)):
    """Windows Terminal 새 탭 또는 PowerShell 새 창에서 cldp 실행.

    실행 우선순위:
    1. wt.exe new-tab + pwsh + cldp  (Windows Terminal 있고 PowerShell 7 있을 때)
    2. pwsh.exe 새 콘솔 + cldp
    3. powershell.exe 새 콘솔 + cldp
    """
    require_token(x_token)
    folder = Path(body.folder)
    if not folder.exists():
        log.warning("폴더 없음: %s", folder)
        raise HTTPException(status_code=404, detail=f"폴더 없음: {folder}")

    folder_str = str(folder)
    title = body.project_id or folder.name

    errors = []

    # 시도 1: Windows Terminal + pwsh
    if WT and "pwsh" in PWSH.lower():
        try:
            args = [
                WT, "new-tab",
                "--title", title,
                "-d", folder_str,
                PWSH, "-NoExit", "-Command", "cldp",
            ]
            log.info("터미널 시도(wt): %s", " ".join(args))
            subprocess.Popen(args)
            append_log(f"💬 [{title}] cldp 시작 (wt)")
            return {"ok": True, "via": "wt", "folder": folder_str}
        except Exception as e:
            errors.append(f"wt 실패: {e}")
            log.error("wt 실행 실패: %s", e)

    # 시도 2: pwsh.exe 새 콘솔
    try:
        args = [PWSH, "-NoExit", "-WorkingDirectory", folder_str, "-Command", "cldp"]
        log.info("터미널 시도(pwsh): %s", " ".join(args))
        subprocess.Popen(args, creationflags=subprocess.CREATE_NEW_CONSOLE)
        append_log(f"💬 [{title}] cldp 시작 (pwsh)")
        return {"ok": True, "via": "pwsh", "folder": folder_str}
    except Exception as e:
        errors.append(f"pwsh 실패: {e}")
        log.error("pwsh 실행 실패: %s\n%s", e, traceback.format_exc())

    raise HTTPException(status_code=500, detail="; ".join(errors))


@app.post("/api/categories")
def add_category(body: CategoryIn, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    data = load_projects_data()
    cid = body.id or slugify(body.name)
    if any(c["id"] == cid for c in data["categories"]):
        raise HTTPException(status_code=409, detail="카테고리 ID 중복")
    cat = {
        "id": cid,
        "name": body.name,
        "icon": body.icon or "📁",
        "color": body.color or "#6b7280",
    }
    data["categories"].append(cat)
    save_projects_data(data)
    append_log(f"➕ 카테고리 추가: {cat['name']}")
    return cat


@app.delete("/api/categories/{cat_id}")
def delete_category(cat_id: str, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    data = load_projects_data()
    used = [p for p in data["projects"] if p["category"] == cat_id]
    if used:
        raise HTTPException(status_code=409, detail=f"카테고리 사용 중: {len(used)}개 프로젝트")
    before = len(data["categories"])
    data["categories"] = [c for c in data["categories"] if c["id"] != cat_id]
    if len(data["categories"]) == before:
        raise HTTPException(status_code=404, detail="카테고리 없음")
    save_projects_data(data)
    return {"ok": True}


@app.patch("/api/categories/{cat_id}")
def update_category(cat_id: str, body: CategoryPatch, x_token: Optional[str] = Header(default=None)):
    """카테고리 이름/아이콘/색 수정. id는 불변(메뉴 anchor 호환)."""
    require_token(x_token)
    data = load_projects_data()
    cat = next((c for c in data["categories"] if c["id"] == cat_id), None)
    if not cat:
        raise HTTPException(status_code=404, detail="카테고리 없음")
    if body.name is not None: cat["name"] = body.name
    if body.icon is not None: cat["icon"] = body.icon
    if body.color is not None: cat["color"] = body.color
    save_projects_data(data)
    append_log(f"✏ 카테고리 수정: {cat['name']}")
    return cat


@app.post("/api/projects-meta")
def add_project(body: ProjectIn, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    data = load_projects_data()
    if not any(c["id"] == body.category for c in data["categories"]):
        raise HTTPException(status_code=400, detail="카테고리 없음")
    pid = body.id or slugify(body.name)
    if any(p["id"] == pid for p in data["projects"]):
        pid = pid + "-" + secrets.token_hex(2)
    item = {
        "id": pid,
        "name": body.name,
        "category": body.category,
        "folder": body.folder,
        "url": body.url,
        "note": body.note or "",
    }
    data["projects"].append(item)
    save_projects_data(data)
    append_log(f"➕ 프로젝트 추가: {item['name']}")
    return item


@app.post("/api/projects-order")
def reorder_projects(body: OrderIn, x_token: Optional[str] = Header(default=None)):
    """projects 배열 전체 순서를 받은 ids 순서대로 재정렬."""
    require_token(x_token)
    data = load_projects_data()
    by_id = {p["id"]: p for p in data["projects"]}
    new_order = []
    seen = set()
    for pid in body.ids:
        if pid in by_id and pid not in seen:
            new_order.append(by_id[pid])
            seen.add(pid)
    # 빠진 거 뒤에 붙임
    for p in data["projects"]:
        if p["id"] not in seen:
            new_order.append(p)
    data["projects"] = new_order
    save_projects_data(data)
    return {"ok": True, "count": len(new_order)}


@app.delete("/api/projects-meta/{project_id}")
def delete_project(project_id: str, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    data = load_projects_data()
    before = len(data["projects"])
    data["projects"] = [p for p in data["projects"] if p["id"] != project_id]
    if len(data["projects"]) == before:
        raise HTTPException(status_code=404, detail="프로젝트 없음")
    save_projects_data(data)
    return {"ok": True}


@app.patch("/api/projects-meta/{project_id}")
def update_project(project_id: str, body: ProjectPatch, x_token: Optional[str] = Header(default=None)):
    """프로젝트 메타 수정 (카테고리 이동, 이름·폴더·URL·노트 변경)."""
    require_token(x_token)
    data = load_projects_data()
    p = next((p for p in data["projects"] if p["id"] == project_id), None)
    if not p:
        raise HTTPException(status_code=404, detail="프로젝트 없음")
    if body.category is not None:
        if not any(c["id"] == body.category for c in data["categories"]):
            raise HTTPException(status_code=400, detail="카테고리 없음")
        p["category"] = body.category
    if body.name is not None: p["name"] = body.name
    if body.folder is not None: p["folder"] = body.folder
    if body.url is not None: p["url"] = body.url
    if body.note is not None: p["note"] = body.note
    save_projects_data(data)
    append_log(f"✏ 프로젝트 수정: {p['name']}")
    return p


@app.get("/api/bookmarks")
def get_bookmarks(x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    items = load_bookmarks()
    # 폴더 존재 여부 / 수정 시각 부착
    for b in items:
        try:
            f = Path(b["folder"])
            b["exists"] = f.exists()
            b["last_modified"] = int(f.stat().st_mtime) if b["exists"] else None
        except Exception:
            b["exists"] = False
            b["last_modified"] = None
    return {"bookmarks": items}


@app.post("/api/bookmarks")
def add_bookmark(body: Bookmark, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    folder_str = body.folder.strip().strip('"').strip("'")
    folder = Path(folder_str)
    if not folder.exists():
        raise HTTPException(status_code=404, detail=f"폴더 없음: {folder}")
    items = load_bookmarks()
    # 중복 체크
    for b in items:
        if Path(b["folder"]).resolve() == folder.resolve():
            raise HTTPException(status_code=409, detail="이미 등록된 폴더")
    item = {
        "id": secrets.token_hex(6),
        "folder": str(folder),
        "name": body.name or folder.name,
        "note": body.note or "",
        "category": body.category or "tool",
        "added_at": int(dt.datetime.now().timestamp()),
    }
    items.insert(0, item)  # 최신순
    save_bookmarks(items)
    append_log(f"📌 폴더 바로가기 추가: {item['name']} ({folder})")
    return item


class BookmarkPatch(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    note: Optional[str] = None


@app.patch("/api/bookmarks/{bookmark_id}")
def update_bookmark(bookmark_id: str, body: BookmarkPatch, x_token: Optional[str] = Header(default=None)):
    """폴더 바로가기 카테고리 이동 / 이름·노트 수정 (칩 드래그용)."""
    require_token(x_token)
    items = load_bookmarks()
    b = next((b for b in items if b.get("id") == bookmark_id), None)
    if not b:
        raise HTTPException(status_code=404, detail="바로가기 없음")
    if body.name is not None: b["name"] = body.name
    if body.category is not None: b["category"] = body.category
    if body.note is not None: b["note"] = body.note
    save_bookmarks(items)
    return b


def _norm_path(p: str) -> str:
    """경로 비교용 정규화 (대소문자·끝 슬래시 무시)."""
    try:
        return str(Path(p)).rstrip("\\/").lower()
    except Exception:
        return (p or "").rstrip("\\/").lower()


@app.post("/api/bookmarks-import")
def import_desktop(x_token: Optional[str] = Header(default=None)):
    """바탕화면 폴더 바로가기 + 실제 폴더를 스캔해 자동 분류로 일괄 추가.

    이미 프로젝트로 등록된 폴더, 이미 바로가기에 있는 폴더는 건너뛴다.
    """
    require_token(x_token)
    scanned = desktop_scan.scan_desktop()
    proj_data = load_projects_data()
    existing = {_norm_path(p["folder"]) for p in proj_data.get("projects", [])}
    items = load_bookmarks()
    for b in items:
        existing.add(_norm_path(b["folder"]))

    added = 0
    skipped = 0
    for it in scanned:
        folder = it.get("path", "")
        name = it.get("name", "")
        if not folder or _norm_path(folder) in existing:
            skipped += 1
            continue
        items.append({
            "id": secrets.token_hex(6),
            "folder": folder,
            "name": name,
            "note": "",
            "category": desktop_scan.classify(name, folder),
            "added_at": int(dt.datetime.now().timestamp()),
        })
        existing.add(_norm_path(folder))
        added += 1

    save_bookmarks(items)
    append_log(f"🖥 바탕화면 가져오기: {added}개 추가 · {skipped}개 중복 스킵")
    return {"added": added, "skipped": skipped, "total": len(items)}


@app.post("/api/bookmarks-order")
def reorder_bookmarks(body: OrderIn, x_token: Optional[str] = Header(default=None)):
    """폴더 바로가기 전체 순서를 받은 ids 순서대로 재정렬 (칩 드래그용)."""
    require_token(x_token)
    items = load_bookmarks()
    by_id = {b["id"]: b for b in items}
    new_order = []
    seen = set()
    for bid in body.ids:
        if bid in by_id and bid not in seen:
            new_order.append(by_id[bid])
            seen.add(bid)
    for b in items:  # 빠진 건 뒤에 보존
        if b["id"] not in seen:
            new_order.append(b)
    save_bookmarks(new_order)
    return {"ok": True, "count": len(new_order)}


@app.delete("/api/bookmarks/{bookmark_id}")
def delete_bookmark(bookmark_id: str, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    items = load_bookmarks()
    new_items = [b for b in items if b.get("id") != bookmark_id]
    if len(new_items) == len(items):
        raise HTTPException(status_code=404, detail="책갈피 없음")
    save_bookmarks(new_items)
    return {"ok": True}


@app.post("/api/log")
def post_log(entry: LogEntry, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    tag = f"[{entry.project_id}] " if entry.project_id else ""
    append_log(f"📝 {tag}{entry.message}")
    return {"ok": True}


@app.get("/api/logs/today")
def logs_today(x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    today = dt.date.today().isoformat()
    log_file = LOG_DIR / f"{today}.md"
    if not log_file.exists():
        return {"date": today, "content": ""}
    return {"date": today, "content": log_file.read_text(encoding="utf-8")}


@app.get("/api/logs/recent")
def logs_recent(days: int = 7, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    result = []
    for log_file in sorted(LOG_DIR.glob("*.md"), reverse=True)[:days]:
        result.append({"date": log_file.stem, "content": log_file.read_text(encoding="utf-8")})
    return {"logs": result}


# ---------- 정적 파일 (web/) ----------

@app.get("/")
def root():
    index = WEB_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"error": "web/index.html not found"}, status_code=404)


@app.get("/harness.html")
def harness_page():
    page = WEB_DIR / "harness.html"
    if page.exists():
        return FileResponse(page)
    return JSONResponse({"error": "web/harness.html not found"}, status_code=404)


app.mount("/assets", StaticFiles(directory=str(WEB_DIR / "assets")), name="assets")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("MINTSPACE_PORT", "5500"))
    print(f"\n  민티스페이스 헬퍼 v0.2.0")
    print(f"  http://localhost:{port}")
    print(f"  토큰: {TOKEN}\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
