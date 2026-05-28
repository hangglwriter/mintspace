"""logs 분석 → 자동 별표 추천.

최근 N일 작업 로그(`data/logs/YYYY-MM-DD.md`)를 읽어:
- 자주 연 바로가기 (≥ threshold 번) 중 별표 안 된 것 → 별표 추천
- 별표돼 있지만 N일간 0번 → 해제 추천

server.py `/api/star-suggestions` 에서 호출.
"""

from __future__ import annotations

import datetime as dt
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = ROOT / "data" / "logs"

# 로그 항목 예시:
#   - 10:09  📂 [bm-9210c8ae5f46] 폴더 열림
#   - 11:58  📂 [storywinner] 폴더 열림
#   - 12:00  💬 [storywinner] cldp 시작 (wt)
# 첫 [...] 안의 tag 만 본다. bm- 접두면 bookmark, 그 외는 project.
_TAG_RE = re.compile(r"\[([^\]]+)\]")


def count_opens(days: int = 7) -> Counter:
    """최근 days 일 로그에서 (kind, id) 별 카운트 (폴더 열기 + cldp 시작 통합)."""
    today = dt.date.today()
    cnt: Counter = Counter()
    for offset in range(days):
        d = today - dt.timedelta(days=offset)
        f = LOG_DIR / f"{d.isoformat()}.md"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = _TAG_RE.search(line)
            if not m:
                continue
            tag = m.group(1)
            if tag.startswith("bm-"):
                cnt[("bookmark", tag[3:])] += 1
            else:
                cnt[("project", tag)] += 1
    return cnt


def suggest(bookmarks: list, projects: list | None = None,
            days: int = 7, threshold: int = 5, project_top_n: int = 5) -> dict:
    """별표 추가 / 해제 추천 + 자주 작업한 프로젝트 TOP.

    Args:
        bookmarks: 현재 bookmarks.json 리스트 (id, name, category, starred 포함)
        projects: 현재 projects.json projects 리스트 (참고용 TOP 추출)
        days: 분석 기간 (일)
        threshold: 별표 추천 최소 횟수
        project_top_n: 프로젝트 TOP 몇 개 보여줄지

    Returns dict:
        star_recommend: 자주 열었는데 별표 안 됨 (적용 가능)
        unstar_recommend: 별표돼 있는데 days 일간 0번 (적용 가능)
        project_top: 이번 주 자주 작업한 프로젝트 TOP N (참고용, 별표 미지원)
    """
    cnt = count_opens(days)
    bm_by_id = {b["id"]: b for b in bookmarks}
    pj_by_id = {p["id"]: p for p in (projects or [])}

    # 1) 별표 추가 추천
    star_rec = []
    for (kind, id_), n in cnt.most_common():
        if kind != "bookmark":
            continue
        if n < threshold:
            break
        b = bm_by_id.get(id_)
        if not b or b.get("starred"):
            continue
        star_rec.append({
            "id": id_,
            "name": b.get("name", id_),
            "category": b.get("category"),
            "type": b.get("type", "folder"),
            "count": n,
        })

    # 2) 별표 해제 추천: 별표돼 있는데 days 일간 0번
    unstar_rec = []
    for b in bookmarks:
        if not b.get("starred"):
            continue
        n = cnt.get(("bookmark", b["id"]), 0)
        if n == 0:
            unstar_rec.append({
                "id": b["id"],
                "name": b.get("name", b["id"]),
                "category": b.get("category"),
                "type": b.get("type", "folder"),
                "count": 0,
            })

    # 3) 자주 작업한 프로젝트 TOP (정보 표시용 - 별표 미지원이라 적용 불가)
    project_top = []
    for (kind, id_), n in cnt.most_common():
        if kind != "project":
            continue
        p = pj_by_id.get(id_)
        if not p:
            continue
        project_top.append({
            "id": id_,
            "name": p.get("name", id_),
            "category": p.get("category"),
            "count": n,
        })
        if len(project_top) >= project_top_n:
            break

    return {
        "days": days,
        "threshold": threshold,
        "star_recommend": star_rec,
        "unstar_recommend": unstar_rec,
        "project_top": project_top,
    }


if __name__ == "__main__":
    # CLI 디버그
    import json
    bms = json.loads((ROOT / "data" / "bookmarks.json").read_text(encoding="utf-8"))
    pjs = json.loads((ROOT / "data" / "projects.json").read_text(encoding="utf-8"))["projects"]
    result = suggest(bms, pjs)
    print(f"최근 {result['days']}일 / 임계 {result['threshold']}번")
    print(f"\n[별표 추가 추천 {len(result['star_recommend'])}개]")
    for r in result["star_recommend"]:
        print(f"  {r['count']}회 · {r['name']} ({r['category']})")
    print(f"\n[별표 해제 추천 {len(result['unstar_recommend'])}개]")
    for r in result["unstar_recommend"]:
        print(f"  {r['name']} ({r['category']})")
    print(f"\n[이번 주 자주 작업한 프로젝트 TOP {len(result['project_top'])}]")
    for r in result["project_top"]:
        print(f"  {r['count']}회 · {r['name']} ({r['category']})")
