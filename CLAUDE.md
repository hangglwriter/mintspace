# 민티스페이스 (D:\Sites\mintspace)

> 민티 전용 데스크탑 워크스페이스. 모든 프로젝트 폴더/문서/링크를 한 화면에서 관리 + 클릭 한 번에 열기.

## 구조

- **화면** (`web/`) = Vercel 정적 배포. `git push` 해야 화면 반영. 메모리 [[mintspace-vercel-frontend]] 참고.
- **API** (`helper/server.py`) = FastAPI 로컬 헬퍼. http://localhost:5500. `start.bat` 더블클릭 또는 `start-helper.ps1` 로 기동.
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

### 다음 할 것
- [ ] 바탕화면 스캔에 파일 포함 옵션 (지금은 폴더만 일괄 수집; 파일은 모달로 개별 추가)
- [ ] 즐겨찾기 섹션 카드도 드래그로 카테고리/순서 변경
- [ ] 카드 노트(메모) 편집 UI - 서버 PATCH note 는 이미 지원, 모달 UI 만 추가
- [ ] 카테고리 자체 순서 변경 (지금은 추가 순서대로 고정)
- [ ] 검색 결과에서 카테고리 헤더 보존 (일부 섹션이 숨겨질 수 있음)

## API 라우트 (helper/server.py)

- **프로젝트(큰 카드)**: GET `/api/projects` · POST/PATCH/DELETE `/api/projects-meta/{id}` · POST `/api/projects-order`
- **카테고리**: POST `/api/categories` · PATCH/DELETE `/api/categories/{id}`
- **바로가기(미니카드)**: GET/POST `/api/bookmarks` · PATCH/DELETE `/api/bookmarks/{id}` · POST `/api/bookmarks-order` · POST `/api/bookmarks-import` (바탕화면 스캔)
- **액션**: POST `/api/open-folder` (폴더/파일 둘 다 `os.startfile`) · POST `/api/launch-terminal` (cldp)
- **인증**: POST `/api/token-bootstrap` (로컬 IP 에서만 자동 발급)
- **헬스**: GET `/api/health`

## 주의

- 데이터 파일 `.gitignore` 이라 다른 PC / 배포에선 빈 상태로 보임 (NAS 경로 노출 방지 의도)
- 외부(Vercel) 접속 시엔 사이드바 ⚙ 설정에서 헬퍼 URL + 토큰 입력 필요
- 헬퍼 재시작 필요 시점: `server.py` / `desktop_scan.py` 변경 시. 정적 파일(html/js/css) 만 바뀌면 새로고침으로 충분
- **캐시 버스팅**: `web/index.html` 의 `?v=YYYYMMDDNN` 버전 안 올리면 브라우저가 옛 js/css 사용 (현재 `?v=2026052808`)
- bat 파일 직접 수정 금지 (CP949+CRLF 인코딩 필요. Python 으로 저장하거나 PowerShell 분리)

## 관련 메모리

- [[mintspace-vercel-frontend]] - Vercel 배포 구조 (화면 Vercel, API 로컬)
- [[mintspace-folder-shortcuts]] - 바로가기 시스템 운영 지식 (type 판별, 분류 규칙, gitignore)
