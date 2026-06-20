"""민티스페이스 로컬 헬퍼 (FastAPI).

브라우저 대시보드(로컬 또는 배포)에서 호출하는 API.
- 폴더 탐색기 열기
- Windows Terminal + PowerShell 7 + cldp 실행
- 프로젝트 메타 / 작업 로그 관리
"""

from __future__ import annotations

import sys as _sys

# pythonw.exe(콘솔 없음)로 띄우면 sys.stdout/stderr 가 None 이라
# uvicorn 컬러 로깅의 sys.stdout.isatty() 에서 죽는다. 더미로 채워 방지.
import os as _os
if _sys.stdout is None:
    _sys.stdout = open(_os.devnull, "w", encoding="utf-8")
if _sys.stderr is None:
    _sys.stderr = open(_os.devnull, "w", encoding="utf-8")

import datetime as dt
import json
import logging
import os
import re
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
import auto_star

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
    # Chrome PNA(Private Network Access): HTTPS(Vercel) → localhost 헬퍼 접근 시
    # 브라우저가 preflight 에 'Access-Control-Request-Private-Network: true' 를 붙여 보냄.
    # 이 옵션이 없으면 Starlette CORSMiddleware 가 400 "Disallowed CORS private-network" 로
    # 거부 → Vercel 화면에서 바로가기가 안 뜸. (메모리 [[mintspace-pna-localhost]])
    allow_private_network=True,
)


def require_token(x_token: Optional[str]) -> None:
    if x_token != TOKEN:
        raise HTTPException(status_code=401, detail="invalid token")


class ProjectRef(BaseModel):
    folder: str
    project_id: Optional[str] = None
    new_window: bool = False  # True = 새 wt 창(새 그룹), False = 최근 창에 탭


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
    starred: Optional[bool] = None


class GroupIn(BaseModel):
    id: Optional[str] = None
    name: str
    icon: Optional[str] = None
    project_ids: list[str] = []


class GroupPatch(BaseModel):
    name: Optional[str] = None
    icon: Optional[str] = None
    project_ids: Optional[list[str]] = None


def load_projects_data() -> dict:
    if not PROJECTS_FILE.exists():
        return {"categories": [], "projects": [], "links": [], "groups": []}
    data = json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
    data.setdefault("groups", [])  # 기존 파일 호환 (탭 그룹은 나중에 추가됨)
    return data


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
    # 각 프로젝트에 폴더 메타 + starred 자동 부착 (기존 데이터 호환)
    for p in data.get("projects", []):
        if "starred" not in p:
            p["starred"] = False
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


def _allow_foreground() -> None:
    """다음에 띄울 자식 프로세스(wt)가 자기 창을 포그라운드로 올릴 수 있게 허용.

    pythonw(콘솔 없는 백그라운드)에서 Popen 하면 Windows 의 foreground lock 때문에
    wt 가 기존 mintspace 창에 탭을 붙여도 앞으로 못 나오고 작업표시줄만 깜빡인다.
    ASFW_ANY(-1) 로 권한을 풀어주면 깜빡임 없이 올라온다. 실패해도 치명적이지 않음.
    """
    try:
        import ctypes
        ctypes.windll.user32.AllowSetForegroundWindow(-1)  # ASFW_ANY
    except Exception as e:  # noqa: BLE001
        log.debug("AllowSetForegroundWindow 실패(무시): %s", e)


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
            # 창 타겟: 새 창(새 그룹) vs 가장 최근 wt 창에 탭(-w 0).
            #   new_window=True  → -w new  : 새 창 생성 → 이게 "최근 창"이 됨
            #   new_window=False → -w 0    : 방금/마지막으로 쓰던 창에 탭으로 붙음
            # 워크플로: Shift+클릭으로 새 창 한 번 열고, 이후 클릭들은 그 창에 탭.
            win = "new" if body.new_window else "0"
            args = [
                WT, "-w", win, "new-tab",
                "--title", title,
                "-d", folder_str,
                PWSH, "-NoExit", "-Command", "cldp",
            ]
            log.info("터미널 시도(wt): %s", " ".join(args))
            # pythonw(백그라운드)는 다른 창을 앞으로 못 끌어옴(작업표시줄만 깜빡).
            # Popen 직전 자식에게 포그라운드 권한을 넘겨 깜빡임 없이 올라오게.
            _allow_foreground()
            subprocess.Popen(args)
            append_log(f"💬 [{title}] cldp 시작 (wt, {'새창' if body.new_window else '탭'})")
            return {"ok": True, "via": "wt", "folder": folder_str,
                    "window": "new" if body.new_window else "tab"}
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


# ─────────────────────────── 탭 그룹 ───────────────────────────
# 자주 같이 여는 프로젝트들을 묶어 새 창 하나에 cldp 탭으로 한 번에 펼침.

def _cldp_tab(folder_str: str, title: str) -> list:
    """wt new-tab 서브커맨드 한 조각 (cldp 실행)."""
    return ["new-tab", "--title", title, "-d", folder_str,
            PWSH, "-NoExit", "-Command", "cldp"]


@app.get("/api/groups")
def list_groups(x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    return load_projects_data().get("groups", [])


@app.post("/api/groups")
def add_group(body: GroupIn, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    data = load_projects_data()
    data.setdefault("groups", [])
    gid = body.id or slugify(body.name) or secrets.token_hex(3)
    if any(g["id"] == gid for g in data["groups"]):
        gid = gid + "-" + secrets.token_hex(2)
    group = {
        "id": gid,
        "name": body.name,
        "icon": body.icon or "🗂",
        "project_ids": body.project_ids or [],
    }
    data["groups"].append(group)
    save_projects_data(data)
    append_log(f"➕ 탭 그룹 추가: {group['name']}")
    return group


@app.patch("/api/groups/{group_id}")
def patch_group(group_id: str, body: GroupPatch, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    data = load_projects_data()
    g = next((g for g in data.get("groups", []) if g["id"] == group_id), None)
    if not g:
        raise HTTPException(status_code=404, detail="그룹 없음")
    if body.name is not None: g["name"] = body.name
    if body.icon is not None: g["icon"] = body.icon
    if body.project_ids is not None: g["project_ids"] = body.project_ids
    save_projects_data(data)
    return g


@app.delete("/api/groups/{group_id}")
def delete_group(group_id: str, x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    data = load_projects_data()
    before = len(data.get("groups", []))
    data["groups"] = [g for g in data.get("groups", []) if g["id"] != group_id]
    if len(data["groups"]) == before:
        raise HTTPException(status_code=404, detail="그룹 없음")
    save_projects_data(data)
    return {"ok": True}


def _open_projects_in_one_window(members: list, label: str) -> dict:
    """members(프로젝트 dict 리스트)를 새 창 하나에 cldp 탭으로 연다.

    그룹 launch · 작업 복원 공통. 폴더 존재 검증은 호출측 책임.
    """
    # 시도 1: Windows Terminal — 새 창 1개 + new-tab 들을 ';' 로 이어붙임
    if WT and "pwsh" in PWSH.lower():
        try:
            args = [WT, "-w", "new"]
            for i, p in enumerate(members):
                if i > 0:
                    args.append(";")  # wt 서브커맨드 구분자 → 같은 창에 다음 탭
                args += _cldp_tab(str(Path(p["folder"])), p.get("id") or Path(p["folder"]).name)
            log.info("멀티탭 터미널(wt): %s", " ".join(args))
            _allow_foreground()
            subprocess.Popen(args)
            append_log(f"🗂 [{label}] cldp {len(members)}개 탭 시작")
            return {"ok": True, "via": "wt", "opened": len(members)}
        except Exception as e:
            log.error("멀티탭 wt 실행 실패: %s\n%s", e, traceback.format_exc())
            # 폴백으로 진행

    # 시도 2: WT 없음 → 각각 새 콘솔로 (탭은 못 묶지만 일단 열기)
    opened = 0
    for p in members:
        try:
            subprocess.Popen(
                [PWSH, "-NoExit", "-WorkingDirectory", str(Path(p["folder"])), "-Command", "cldp"],
                creationflags=subprocess.CREATE_NEW_CONSOLE,
            )
            opened += 1
        except Exception as e:
            log.error("멀티탭 pwsh 실행 실패(%s): %s", p.get("id"), e)
    if not opened:
        raise HTTPException(status_code=500, detail="터미널 실행 실패")
    append_log(f"🗂 [{label}] cldp {opened}개 (개별 창)")
    return {"ok": True, "via": "pwsh", "opened": opened}


@app.post("/api/groups/{group_id}/launch")
def launch_group(group_id: str, x_token: Optional[str] = Header(default=None)):
    """그룹의 모든 프로젝트 cldp 를 새 창 하나에 탭으로 한꺼번에 연다."""
    require_token(x_token)
    data = load_projects_data()
    g = next((g for g in data.get("groups", []) if g["id"] == group_id), None)
    if not g:
        raise HTTPException(status_code=404, detail="그룹 없음")

    by_id = {p["id"]: p for p in data.get("projects", [])}
    members, skipped = [], []
    for pid in g.get("project_ids", []):
        p = by_id.get(pid)
        if p and Path(p["folder"]).exists():
            members.append(p)
        else:
            skipped.append(pid)
    if not members:
        raise HTTPException(status_code=400, detail="열 수 있는 프로젝트가 없음 (폴더 없음/멤버 없음)")

    res = _open_projects_in_one_window(members, g["name"])
    res["skipped"] = skipped
    return res


# ─────────────────────────── 작업 복원 ───────────────────────────
# logs/*.md 의 cldp launch 기록(- HH:MM  💬 [project_id] cldp ...)을 읽어
# 마지막 작업 세션(최근 launch 시각부터 window 분 안)에 연 프로젝트를 복원.

_LAUNCH_RE = re.compile(r"^- (\d{2}):(\d{2})\s+💬 \[(.+?)\] cldp")


def _recent_launch_pids(window_min: int = 2880) -> list:
    """최근 로그에서 마지막 cldp launch 시각부터 window_min 분 안의 project_id 목록 (최근 연 순, 중복 제거).
    기본 2880분 = 48시간(2일). 자정 경계로 날짜가 여러 개 걸리고 작업 안 한 날은 파일이 없으므로
    넉넉히 최근 8개 로그 파일을 읽은 뒤 cutoff 로 필터링한다."""
    entries = []  # (datetime, project_id)
    for lf in sorted(LOG_DIR.glob("*.md"), reverse=True)[:8]:
        try:
            d = dt.date.fromisoformat(lf.stem)
        except ValueError:
            continue
        for line in lf.read_text(encoding="utf-8").splitlines():
            m = _LAUNCH_RE.match(line)
            if m:
                hh, mm, pid = int(m.group(1)), int(m.group(2)), m.group(3)
                entries.append((dt.datetime.combine(d, dt.time(hh, mm)), pid))
    if not entries:
        return []
    entries.sort(key=lambda e: e[0])
    cutoff = entries[-1][0] - dt.timedelta(minutes=window_min)
    # 윈도우 안 + 최근에 연 순(역순) + 중복 제거
    seen, ordered = set(), []
    for t, pid in reversed(entries):
        if t < cutoff:
            break
        if pid not in seen:
            seen.add(pid)
            ordered.append(pid)
    return ordered


@app.get("/api/restore-candidates")
def restore_candidates(window: int = 2880, x_token: Optional[str] = Header(default=None)):
    """마지막 작업 세션에 연 프로젝트 후보 목록 (이름/폴더/존재여부 포함)."""
    require_token(x_token)
    data = load_projects_data()
    by_id = {p["id"]: p for p in data.get("projects", [])}
    out = []
    for pid in _recent_launch_pids(window):
        p = by_id.get(pid)
        if p:
            out.append({
                "id": pid,
                "name": p.get("name", pid),
                "folder": p["folder"],
                "exists": Path(p["folder"]).exists(),
            })
        # 프로젝트로 매칭 안 되는 id(삭제됨/folder.name 등)는 복원 불가라 제외
    return {"window": window, "candidates": out}


@app.post("/api/restore-launch")
def restore_launch(body: OrderIn, x_token: Optional[str] = Header(default=None)):
    """선택한 project_id 들을 새 창 하나에 cldp 탭으로 복원."""
    require_token(x_token)
    data = load_projects_data()
    by_id = {p["id"]: p for p in data.get("projects", [])}
    members, skipped = [], []
    for pid in body.ids:
        p = by_id.get(pid)
        if p and Path(p["folder"]).exists():
            members.append(p)
        else:
            skipped.append(pid)
    if not members:
        raise HTTPException(status_code=400, detail="복원할 수 있는 프로젝트가 없음")
    res = _open_projects_in_one_window(members, "작업 복원")
    res["skipped"] = skipped
    return res


# ─────────────────────────── 폴더 작업 복원 ───────────────────────────
# logs/*.md 의 폴더 열기 기록(- HH:MM  📂 [id] 폴더 열림)을 읽어 마지막 세션에
# 연 폴더(큰 카드 + 미니카드)를 복원. cldp 복원과 판박이지만 실행은 탭이 아니라
# 각각 새 탐색기 창(explorer 는 탭 제어 API 가 없어 한 창에 못 묶음).
# id 규칙: "bm-XXX" = 미니카드(bookmark), 그 외 = 프로젝트(큰 카드). open_folder 가
# project_id 로 그렇게 찍는다(app.js: project=p.id, bookmark="bm-"+b.id).

_FOLDER_RE = re.compile(r"^- (\d{2}):(\d{2})\s+📂 \[(.+?)\] 폴더 열림")


def _recent_folder_opens(window_min: int = 2880) -> list:
    """최근 로그에서 마지막 폴더 열기 시각부터 window_min 분 안의 id 목록 (최근 연 순, 중복 제거).
    cldp 복원(_recent_launch_pids)과 동일하게 최근 8개 로그 파일을 읽고 cutoff 로 거른다."""
    entries = []  # (datetime, id)
    for lf in sorted(LOG_DIR.glob("*.md"), reverse=True)[:8]:
        try:
            d = dt.date.fromisoformat(lf.stem)
        except ValueError:
            continue
        for line in lf.read_text(encoding="utf-8").splitlines():
            m = _FOLDER_RE.match(line)
            if m:
                hh, mm, fid = int(m.group(1)), int(m.group(2)), m.group(3)
                entries.append((dt.datetime.combine(d, dt.time(hh, mm)), fid))
    if not entries:
        return []
    entries.sort(key=lambda e: e[0])
    cutoff = entries[-1][0] - dt.timedelta(minutes=window_min)
    seen, ordered = set(), []
    for t, fid in reversed(entries):
        if t < cutoff:
            break
        if fid not in seen:
            seen.add(fid)
            ordered.append(fid)
    return ordered


def _resolve_folder_id(fid: str, by_pid: dict, by_bid: dict):
    """로그 id → (name, folder). 'bm-' 접두면 미니카드, 아니면 프로젝트. 못 찾으면 None."""
    if fid.startswith("bm-"):
        b = by_bid.get(fid[3:])
        if b:
            return (b.get("name") or Path(b["folder"]).name), b["folder"]
        return None
    p = by_pid.get(fid)
    if p:
        return p.get("name", fid), p["folder"]
    return None


@app.get("/api/restore-folders")
def restore_folders(window: int = 2880, x_token: Optional[str] = Header(default=None)):
    """마지막 세션에 연 폴더 후보 목록 (큰 카드 + 미니카드, 최근순)."""
    require_token(x_token)
    data = load_projects_data()
    by_pid = {p["id"]: p for p in data.get("projects", [])}
    by_bid = {b["id"]: b for b in load_bookmarks() if b.get("id")}
    out = []
    for fid in _recent_folder_opens(window):
        r = _resolve_folder_id(fid, by_pid, by_bid)
        if r:
            name, folder = r
            out.append({
                "id": fid,
                "name": name,
                "folder": folder,
                "exists": Path(folder).exists(),
            })
        # 매칭 안 되는 id(삭제된 카드 등)는 복원 불가라 제외
    return {"window": window, "candidates": out}


@app.post("/api/restore-folders-launch")
def restore_folders_launch(body: OrderIn, x_token: Optional[str] = Header(default=None)):
    """선택한 폴더 id 들을 각각 탐색기로 연다 (explorer 탭 제어 불가라 개별 창)."""
    require_token(x_token)
    data = load_projects_data()
    by_pid = {p["id"]: p for p in data.get("projects", [])}
    by_bid = {b["id"]: b for b in load_bookmarks() if b.get("id")}
    opened, skipped = 0, []
    for fid in body.ids:
        r = _resolve_folder_id(fid, by_pid, by_bid)
        if not r or not Path(r[1]).exists():
            skipped.append(fid)
            continue
        try:
            os.startfile(r[1])
            opened += 1
        except Exception as e:  # noqa: BLE001
            log.error("폴더 복원 열기 실패(%s): %s", fid, e)
            skipped.append(fid)
    if not opened:
        raise HTTPException(status_code=400, detail="복원할 수 있는 폴더가 없음")
    # 요약 로그(개별 '📂 [id] 폴더 열림' 과 다른 문구 → 다음 복원 후보에 안 섞임)
    append_log(f"🕐 폴더 복원: {opened}개")
    return {"ok": True, "opened": opened, "skipped": skipped}


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
    # 빈 문자열로 오면 None 으로 저장 → 카드에서 🌐 사이트 버튼 제거 (URL 지우기 지원)
    if body.url is not None: p["url"] = body.url or None
    if body.note is not None: p["note"] = body.note
    if body.starred is not None: p["starred"] = body.starred
    save_projects_data(data)
    append_log(f"✏ 프로젝트 수정: {p['name']}")
    return p


@app.get("/api/bookmarks")
def get_bookmarks(x_token: Optional[str] = Header(default=None)):
    require_token(x_token)
    items = load_bookmarks()
    # 존재 여부 / 수정 시각 / type / starred 자동 부착 (기존 데이터 호환)
    for b in items:
        if "starred" not in b:
            b["starred"] = False
        # 줄바꿈 라인: 경로 없음, 검사 스킵
        if b.get("type") == "rowbreak":
            b["exists"] = True
            b["last_modified"] = None
            continue
        if b.get("type") == "link":
            b["exists"] = True
            b["last_modified"] = None
            continue
        try:
            f = Path(b["folder"])
            b["exists"] = f.exists()
            b["last_modified"] = int(f.stat().st_mtime) if b["exists"] else None
            if "type" not in b:
                b["type"] = "file" if f.is_file() else "folder"
        except Exception:
            b["exists"] = False
            b["last_modified"] = None
            if "type" not in b:
                b["type"] = "folder"
    return {"bookmarks": items}


@app.post("/api/bookmarks")
def add_bookmark(body: Bookmark, x_token: Optional[str] = Header(default=None)):
    """폴더 / 파일 / URL 자동 판별해서 미니 카드로 등록."""
    require_token(x_token)
    raw = body.folder.strip().strip('"').strip("'")
    items = load_bookmarks()

    # 1) URL 모드 (링크)
    if raw.startswith(("http://", "https://")):
        norm = raw.rstrip("/").lower()
        for b in items:
            if b.get("type") == "link" and b["folder"].rstrip("/").lower() == norm:
                raise HTTPException(status_code=409, detail="이미 등록된 링크")
        from urllib.parse import urlparse
        host = urlparse(raw).netloc or raw
        item = {
            "id": secrets.token_hex(6),
            "folder": raw,
            "name": body.name or host,
            "note": body.note or "",
            "category": body.category or "tool",
            "type": "link",
            "added_at": int(dt.datetime.now().timestamp()),
        }
        items.insert(0, item)
        save_bookmarks(items)
        append_log(f"🔗 링크 바로가기 추가: {item['name']} ({raw})")
        return item

    # 2) 로컬 경로 모드 (폴더 또는 파일)
    target = Path(raw)
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"경로 없음: {target}")
    is_file = target.is_file()
    for b in items:
        if b.get("type") == "link":
            continue
        try:
            if Path(b["folder"]).resolve() == target.resolve():
                raise HTTPException(status_code=409, detail="이미 등록된 경로")
        except OSError:
            continue
    item = {
        "id": secrets.token_hex(6),
        "folder": str(target),
        "name": body.name or target.name,
        "note": body.note or "",
        "category": body.category or "tool",
        "type": "file" if is_file else "folder",
        "added_at": int(dt.datetime.now().timestamp()),
    }
    items.insert(0, item)
    save_bookmarks(items)
    kind = "📄 파일" if is_file else "📁 폴더"
    append_log(f"📌 {kind} 바로가기 추가: {item['name']} ({target})")
    return item


class RowBreakIn(BaseModel):
    category: str


@app.post("/api/bookmarks-rowbreak")
def add_rowbreak(body: RowBreakIn, x_token: Optional[str] = Header(default=None)):
    """미니카드 사이에 끼우는 '줄바꿈 라인'. 해당 카테고리 끝에 추가됨.

    줄바꿈은 경로가 없는 특수 항목(type=rowbreak)으로, bookmarks 목록에서
    순서만 차지한다. 드래그로 위치 이동, 편집 모드에서 ✕로 제거.
    """
    require_token(x_token)
    items = load_bookmarks()
    item = {
        "id": secrets.token_hex(6),
        "folder": "",
        "name": "",
        "note": "",
        "category": body.category,
        "type": "rowbreak",
        "added_at": int(dt.datetime.now().timestamp()),
    }
    # 같은 카테고리 마지막 항목 바로 뒤에 끼워넣기 (없으면 맨 끝)
    last_idx = -1
    for i, b in enumerate(items):
        if b.get("category") == body.category:
            last_idx = i
    if last_idx >= 0:
        items.insert(last_idx + 1, item)
    else:
        items.append(item)
    save_bookmarks(items)
    append_log(f"➖ 줄바꿈 추가: {body.category}")
    return item


class BookmarkPatch(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    note: Optional[str] = None
    folder: Optional[str] = None
    starred: Optional[bool] = None


@app.patch("/api/bookmarks/{bookmark_id}")
def update_bookmark(bookmark_id: str, body: BookmarkPatch, x_token: Optional[str] = Header(default=None)):
    """폴더 바로가기 카테고리 이동 / 이름·노트·경로 수정 (칩 드래그 + 편집 모달용)."""
    require_token(x_token)
    items = load_bookmarks()
    b = next((b for b in items if b.get("id") == bookmark_id), None)
    if not b:
        raise HTTPException(status_code=404, detail="바로가기 없음")
    if body.name is not None: b["name"] = body.name
    if body.category is not None: b["category"] = body.category
    if body.note is not None: b["note"] = body.note
    if body.starred is not None: b["starred"] = body.starred
    if body.folder is not None:
        raw = body.folder.strip().strip('"').strip("'")
        b["folder"] = raw
        # 경로가 바뀌면 폴더 / 파일 / 링크 종류 재판별
        if raw.startswith(("http://", "https://")):
            b["type"] = "link"
        else:
            try:
                b["type"] = "file" if Path(raw).is_file() else "folder"
            except Exception:
                b["type"] = "folder"
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
            "type": "folder",
            "added_at": int(dt.datetime.now().timestamp()),
        })
        existing.add(_norm_path(folder))
        added += 1

    save_bookmarks(items)
    append_log(f"🖥 바탕화면 가져오기: {added}개 추가 · {skipped}개 중복 스킵")
    return {"added": added, "skipped": skipped, "total": len(items)}


@app.get("/api/star-suggestions")
def star_suggestions(
    days: int = 7,
    threshold: int = 5,
    x_token: Optional[str] = Header(default=None),
):
    """logs 분석으로 자동 별표 추천 + 자주 작업한 프로젝트 TOP."""
    require_token(x_token)
    bookmarks = load_bookmarks()
    proj_data = load_projects_data()
    return auto_star.suggest(
        bookmarks,
        proj_data.get("projects", []),
        days=days,
        threshold=threshold,
    )


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


def _startup_log(msg: str) -> None:
    """자동기동(pythonw, 콘솔 없음) 추적용. silent fail 시 원인 진단 단서를 파일에 남김.
    부팅 시 헬퍼가 안 떴을 때 data/helper-startup.log 를 보면 START/CRASH/STOP 흔적 확인 가능."""
    try:
        with (DATA_DIR / "helper-startup.log").open("a", encoding="utf-8") as f:
            f.write(f"{dt.datetime.now().isoformat(timespec='seconds')}  {msg}\n")
    except Exception:
        pass


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("MINTSPACE_PORT", "5500"))
    print(f"\n  민티스페이스 헬퍼 v0.2.0")
    print(f"  http://localhost:{port}")
    print(f"  토큰: {TOKEN}\n")
    _startup_log(f"START pid={os.getpid()} port={port} exe={_sys.executable}")
    try:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")
    except Exception as e:
        _startup_log(f"CRASH {type(e).__name__}: {e}")
        _startup_log(traceback.format_exc())
        raise
    finally:
        _startup_log("STOP")
