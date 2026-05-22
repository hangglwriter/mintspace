# 민티스페이스 🌿

흩어진 작업 폴더를 한 곳에서 보고, 한 번에 터미널을 띄우는 개인 워크스페이스.

## 구조

```
D:\Sites\mintspace\
├ web\           ← 프론트 (HTML/CSS/JS) — Cloudflare Pages에 배포
├ helper\        ← 로컬 FastAPI 서버 (포트 5500)
├ data\
│  ├ projects.json    ← 프로젝트 메타
│  ├ token.txt        ← 헬퍼 인증 토큰 (자동 생성, 외부 노출 금지)
│  └ logs\            ← 일자별 작업 로그
├ start.bat      ← 헬퍼 시작 + 브라우저 오픈
├ stop.bat       ← 헬퍼 종료
└ create-shortcut.ps1  ← 바탕화면 바로가기 만들기
```

## 시작

```bat
start.bat
```

- 첫 실행: FastAPI/uvicorn 자동 설치
- 헬퍼가 백그라운드에서 돌고 브라우저가 `http://localhost:5500`로 열림
- 끄려면 `stop.bat`

## 바탕화면 바로가기

```powershell
powershell -ExecutionPolicy Bypass -File create-shortcut.ps1
```

## 카드 버튼

| 버튼 | 동작 |
|------|------|
| 📂 폴더 | 파일 탐색기로 폴더 열기 |
| 💬 cldp | Windows Terminal 새 탭에서 `cldp` 자동 실행 |
| 🌐 사이트 | 배포된 사이트를 새 탭으로 (URL이 있을 때만) |

## 키보드

- `/` — 검색창 포커스
- `Esc` — 검색 초기화

## 프로젝트 추가/수정

`data/projects.json` 에 카드 한 줄 추가. `category`는 상단 categories 배열 id 참조.

```json
{ "id": "new-project", "name": "새 프로젝트", "category": "tool",
  "folder": "D:\\new-project", "url": null, "note": "설명" }
```

## 외부 배포 (Cloudflare Pages — Step 2)

- `web/` 만 배포 → 어디서든 로그인해서 접속
- 헬퍼는 작업 컴퓨터에서만 동작 → 모바일에선 보기 전용
- 외부 사이트 접속 시 토큰 입력 모달 → `data/token.txt` 내용 한 번 등록

## 확장 로드맵

- [ ] D1 DB 연결 (작업 로그 영구 저장 + 검색)
- [ ] 노션 API 임베드
- [ ] 자동화 트리거 버튼 (publish.bat, 크롤러)
- [ ] 백그라운드 모니터 (Remotion, Whisper 진행률)
- [ ] Cron Triggers (매주 자동 리포트)
- [ ] 글로벌 단축키 (AutoHotkey)
