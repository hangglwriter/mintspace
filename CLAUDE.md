# 민티스페이스 (D:\Sites\mintspace)

> 민티 전용 데스크탑 워크스페이스. 모든 프로젝트 폴더/문서/링크를 한 화면에서 관리 + 클릭 한 번에 열기.

## 구조

- **화면** (`web/`) = Vercel 정적 배포. `git push` 해야 화면 반영. 메모리 [[mintspace-vercel-frontend]] 참고.
- **API** (`helper/server.py`) = FastAPI 로컬 헬퍼. http://localhost:5500.
  - **기동**: `start.bat` 더블클릭 (또는 윈도우 시작프로그램에 등록돼 있어 부팅 시 자동). 콘솔 안 띄우려면 `pythonw` 로 띄움. 디버깅 땐 `python helper/server.py` (콘솔 로그 보임).
  - ⚠ **pythonw 로 띄우면 `sys.stdout` 이 `None`** → uvicorn 컬러 로깅의 `sys.stdout.isatty()` 에서 죽음(2026-05-30 발견). server.py 상단에서 stdout/stderr None 이면 `os.devnull` 로 채우는 가드로 해결. 이 가드 지우면 자동시작이 silent fail.
  - ⚠ 헬퍼 재시작 시 **절대 포트 강제 종료(`Stop-Process` on 5500) 금지**: 헬퍼가 launch-terminal 로 띄운 cldp 자식 터미널까지 연쇄 사망. 옛 `start-helper.ps1` 이 이 짓을 해서 제거함(2026-05-29). 안전 런처는 "이미 떠 있으면 재기동 안 함" 방식만. (단 cldp 자식이 0개면 그 python 만 단독 종료해도 안전.)
- **데이터** (`data/`) = `.gitignore`. 로컬 전용 (NAS 경로 등 민감).
  - `projects.json` (카테고리 + 큰 카드들 = 클로드 코드로 작업하는 프로젝트)
  - `bookmarks.json` (미니카드 = 폴더/파일/링크 바로가기)
  - `token.txt`, `logs/YYYY-MM-DD.md`

## 현재 상태 (2026-05-29)

### 완료된 큰 기능
- [x] **바탕화면 자동 수집** - `helper/desktop_scan.py` 에서 PowerShell COM(`WScript.Shell`) 으로 `.lnk` 파싱 + 실제 폴더 99개 스캔 → 경로 기반 자동 분류 → bookmarks 일괄 추가 (프로젝트와 중복되는 폴더 자동 제외)
- [x] **카테고리별 미니카드** - 각 카테고리 섹션에 [큰 카드: 프로젝트] + [미니카드: 이름 + 경로 2줄]. 아이콘 3종: 📁 폴더 / 📄 파일 / 🔗 링크
- [x] **카테고리 10종**: 기존 6개(youtube/book/woori/lecture/story/tool) + 추가 4개(chatgpt 💚 / gemini ✨ / drive 💾 / personal 📦)
- [x] **자동 type 판별** - 모달에 경로 입력 시 서버가 자동 분기. `http(s)://` → link, 디렉토리 → folder, 그 외 파일 → file. NAS 한글 경로 (`\\nase...\우리집 정보.hwp`) 정상
- [x] **편집 모드 토글** - 상단 [✎ 편집] → 모든 카드에 빨간 X 배지 + 본문 클릭 비활성 (실수 0). ESC 또는 [✓ 편집 끝] 해제
- [x] **별표/즐겨찾기** - 미니카드 우상단 ☆ 토글 → 페이지 최상단 노란 즐겨찾기 섹션에 카테고리 무관 모임. 사이드바 ⭐ 카운트
- [x] **이름 + 카테고리 편집** - 카드 hover 시 ✏ → 모달에서 표시 이름 + 카테고리 둘 다 변경 (실제 폴더명은 안 바뀜)
- [x] **카테고리 옮기기 3종**: ① 사이드바 카테고리가 드롭존 ② 드래그 중 화면 가장자리(80px) 자동 스크롤 ③ 편집 모달에서 카테고리 드롭다운
- [x] **자동 별표 추천** (`helper/auto_star.py`) - 최근 7일 logs 분석. 자주 여는 bookmark (≥5번) 별표 추천 + 별표 있는데 7일간 0번 해제 추천 + 자주 작업한 프로젝트 TOP 5 인사이트. 상단 [💡 추천 N] 버튼 → 모달
- [x] **프로젝트도 starred 지원** - 큰 카드에도 ☆ 토글 + projects-meta PATCH starred + 즐겨찾기 섹션에 📦 프로젝트 칩으로 렌더 (renderProjectChip). 추천 모달에 kind 필드로 통합 (bookmark/project 둘 다 일괄 별표)
- [x] **카드 편집에 경로 변경** (2026-05-29) - ✏ 편집 모달에 "경로 또는 URL" 칸 추가 (프로젝트 + 미니카드). 미니카드는 경로 바꾸면 폴더/파일/링크 type 자동 재판별 (`BookmarkPatch.folder`)
- [x] **즐겨찾기에 직접 추가 + 줄바꿈** (2026-06-03) - 즐겨찾기 섹션 헤더에 [+ 바로가기] [+ 줄바꿈] 추가. 가상 카테고리 `__fav__`(`FAV_CAT`) 사용 → 실제 카테고리 목록에 없으므로 메인 영역엔 안 뜨고 즐겨찾기에만 렌더(카테고리 무관 "자주 쓰는 링크" 모음). 버튼은 기존 `data-add-bm` / `data-add-rowbreak` 위임 재사용(별도 JS 배선 없음). 바로가기/카드편집 모달 카테고리 드롭다운 맨 위에 "⭐ 즐겨찾기" 옵션(미니카드만, 프로젝트는 서버가 실제 카테고리만 허용). `renderFavorites` = ①`__fav__` 전용(줄바꿈 포함, 순서 유지) ②별표 프로젝트 ③다른 카테고리 별표 미니카드(중복 방지 위해 `__fav__` 제외). favorites-grid 에 `data-sc-cat=__fav__` → 드래그로 즐겨찾기 ↔ 카테고리 끌어 옮기기 + 즐겨찾기 내부 순서변경. 칩 순서 수집을 `#favorites-grid` 포함으로 확장 + Set 중복제거(별표 항목은 자기 카테고리+즐겨찾기 양쪽에 같은 data-bid 로 존재). 서버 변경 없음. 캐시 `?v=2026060301`
- [x] **미니카드 줄바꿈 라인** (2026-05-29) - 카테고리 헤더 [+ 줄바꿈] → `type=rowbreak` 특수 bookmark 추가. CSS `grid-column:1/-1` 로 한 줄 전체 차지 → 뒤 카드 다음 줄로 밀어 줄 단위 그룹화. 드래그로 위치 이동(칩 드래그 시스템에 `.rowbreak` 포함), 편집 모드 ✕로 제거. 순서 수집은 `#categories-area .shortcuts [data-bid]` (즐겨찾기 제외 + rowbreak 포함). 검색/카운트에서 제외. `POST /api/bookmarks-rowbreak`

### 다음 할 것
- [ ] 바탕화면 스캔에 파일 포함 옵션 (지금은 폴더만 일괄 수집; 파일은 모달로 개별 추가)
- [ ] 즐겨찾기 섹션 카드도 드래그로 카테고리/순서 변경
- [ ] 카드 노트(메모) 편집 UI - 서버 PATCH note 는 이미 지원, 모달 UI 만 추가
- [ ] 카테고리 자체 순서 변경 (지금은 추가 순서대로 고정)
- [ ] 검색 결과에서 카테고리 헤더 보존 (일부 섹션이 숨겨질 수 있음)

## API 라우트 (helper/server.py)

- **프로젝트(큰 카드)**: GET `/api/projects` · POST/PATCH/DELETE `/api/projects-meta/{id}` · POST `/api/projects-order`
- **카테고리**: POST `/api/categories` · PATCH/DELETE `/api/categories/{id}`
- **바로가기(미니카드)**: GET/POST `/api/bookmarks` · PATCH/DELETE `/api/bookmarks/{id}` (PATCH 에 folder 도 지원 → type 재판별) · POST `/api/bookmarks-order` · POST `/api/bookmarks-import` (바탕화면 스캔) · POST `/api/bookmarks-rowbreak` (줄바꿈 라인)
- **액션**: POST `/api/open-folder` (폴더/파일 둘 다 `os.startfile`) · POST `/api/launch-terminal` (cldp)
- **추천**: GET `/api/star-suggestions?days=7&threshold=5` (`helper/auto_star.py` logs 분석)
- **인증**: POST `/api/token-bootstrap` (로컬 IP 에서만 자동 발급)
- **헬스**: GET `/api/health`

## 주의

- 데이터 파일 `.gitignore` 이라 다른 PC / 배포에선 빈 상태로 보임 (NAS 경로 노출 방지 의도)
- 외부(Vercel) 접속 시엔 사이드바 ⚙ 설정에서 헬퍼 URL + 토큰 입력 필요
- 헬퍼 재시작 필요 시점: `server.py` / `desktop_scan.py` 변경 시. 정적 파일(html/js/css) 만 바뀌면 새로고침으로 충분
- **캐시 버스팅**: `web/index.html` 의 `?v=YYYYMMDDNN` 버전 안 올리면 브라우저가 옛 js/css 사용 (현재 `?v=2026060301`)
- bat 파일 직접 수정 금지 (CP949+CRLF 인코딩 필요. Python 으로 저장하거나 PowerShell 분리)
- ✅ **안전 start.bat 재구축 (2026-05-30)**: `start.bat` = health 체크 후 "이미 떠 있으면 재기동 안 함" + 강제 종료 절대 안 함 + `pythonw` 절대경로로 기동. 윈도우 시작프로그램(`시작 폴더\mintspace-helper.lnk`, 최소화)에 등록돼 **부팅 시 자동 기동**. 메모리 [[mintspace-helper-restart-footgun]] 참고
- **터미널 띄우기 = 항상 새 창**: `launch-terminal` 이 `wt -w new new-tab` 으로 매번 새 창 생성(2026-05-30 변경). `-w` 없이 `new-tab` 만 쓰면 기존 wt 창에 탭만 붙어 작업표시줄에서 깜빡이기만 함(포커스 안 옴). 새 창이라야 포그라운드로 잘 올라옴.

## 관련 메모리

- [[mintspace-vercel-frontend]] - Vercel 배포 구조 (화면 Vercel, API 로컬)
- [[mintspace-folder-shortcuts]] - 바로가기 시스템 운영 지식 (type 판별, 분류 규칙, gitignore)
- [[mintspace-helper-restart-footgun]] - 헬퍼 재시작 시 포트 강제 종료 금지 (자식 터미널 연쇄 사망)
