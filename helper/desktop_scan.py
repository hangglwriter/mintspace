"""바탕화면 폴더 바로가기 스캔 + 자동 분류.

- 바탕화면의 .lnk 중 '폴더'를 가리키는 것 + 바탕화면에 직접 만든 실제 폴더를 모은다.
- 경로/이름 규칙으로 민티스페이스 카테고리에 자동 배정한다 (이름보다 경로 우선).

server.py 의 import / 재스캔 API 에서 재사용.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

# .lnk(COM) 해석은 PowerShell 에 맡기고, 실제 폴더는 여기서 직접 읽는다.
# ConvertTo-Json 은 한글을 \uXXXX 로 이스케이프하므로 콘솔 인코딩과 무관하게 안전.
_PS_SCRIPT = r"""
$OutputEncoding = [Console]::OutputEncoding = [Text.Encoding]::UTF8
$sh = New-Object -ComObject WScript.Shell
$desktop = [Environment]::GetFolderPath('Desktop')
$result = New-Object System.Collections.ArrayList
Get-ChildItem -LiteralPath $desktop -Filter *.lnk -ErrorAction SilentlyContinue | ForEach-Object {
  try { $t = $sh.CreateShortcut($_.FullName).TargetPath } catch { $t = $null }
  if ($t -and (Test-Path -LiteralPath $t -PathType Container)) {
    $name = $_.BaseName -replace '\s*-\s*바로 가기$',''
    [void]$result.Add(@{ type='lnk'; name=$name; path=$t })
  }
}
Get-ChildItem -LiteralPath $desktop -Directory -ErrorAction SilentlyContinue | ForEach-Object {
  [void]$result.Add(@{ type='dir'; name=$_.Name; path=$_.FullName })
}
$result | ConvertTo-Json -Depth 3 -Compress
"""


def scan_desktop() -> list[dict]:
    """바탕화면의 (폴더 바로가기 + 실제 폴더) 목록을 반환."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", _PS_SCRIPT],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        raw = (out.stdout or "").strip()
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, dict):  # 항목 1개면 dict 로 옴
            data = [data]
        return data
    except Exception:
        return []


def classify(name: str, path: str) -> str:
    """폴더 이름/경로를 보고 카테고리 id 를 정한다. 경로를 이름보다 우선."""
    n = name
    pl = path.lower()

    # 1) ChatGPT / 제미나이 (경로 최우선 — 이름에 챗GPT 들어가도 경로로 판단)
    if pl.startswith("d:\\chatgpt") or ".codex" in pl:
        return "chatgpt"
    if pl.startswith("d:\\gemini") or ".gemini" in pl:
        return "gemini"

    # 2) 우리집 인테리어
    if ("woorijipinterior" in pl or "우리집인테리어" in path or "루피엘" in path
            or "병원" in n or n == "시공처" or "네이버광고" in n
            or n == "블로그 업로드" or "한메디" in n or "개원공간" in n
            or "현장사진" in n or "우리집 관련" in n):
        return "woori"

    # 3) 유튜브 / 콘텐츠 (콘텐츠 업로드 폴더, 영상 자료)
    if ("\\유튜브" in path or "claude-youtube" in pl or "youtube-reports" in pl
            or "행글라이터" in path or "일기콘" in n):
        return "youtube"

    # 4) 강의 / 블로그
    if ("claude-lecture" in pl or "claude-blog" in pl or "특강" in n or "강의" in n
            or "성장 글쓰기 학교" in path or "comfyui" in pl or "리얼북스" in n):
        return "lecture"

    # 5) 책 / 전자책 / 위너책쓰기 / 작가
    if ("위너책쓰기" in path or "ebook-project" in pl or "claude-book" in pl
            or "작가" in n or "출간" in n or "sigil" in pl or "인디자인" in n
            or "책" in n or n[:3] in ("25기", "28기", "29기", "30기", "31기")):
        return "book"

    # 6) 스토리위너 / 앱 / 마케팅
    if ("storywinner" in pl or "스토리위너" in path or "cognitive-game" in pl
            or pl.rstrip("\\").endswith("\\hue") or "포스팅" in path):
        return "story"

    # 7) 드라이브 / 저장소
    if (n in ("다운로드", "스크린샷", "카카오톡 받은 파일", "옮길것")
            or pl == "g:\\" or "google drive" in n.lower() or "동기화" in n):
        return "drive"

    # 8) 개인 / 기타
    if n in ("개인", "무료 AI이미지", "서체 모음", "새폴더템플릿"):
        return "personal"

    # 9) 나머지는 도구 / 개발
    return "tool"


if __name__ == "__main__":
    items = scan_desktop()
    from collections import Counter
    cnt = Counter()
    by_cat: dict[str, list] = {}
    for it in items:
        cat = classify(it["name"], it["path"])
        cnt[cat] += 1
        by_cat.setdefault(cat, []).append(it["name"])
    print(f"총 {len(items)}개\n")
    for cat in sorted(cnt, key=lambda c: -cnt[c]):
        print(f"[{cat}] {cnt[cat]}개")
        for nm in by_cat[cat]:
            print(f"   - {nm}")
        print()
