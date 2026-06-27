# 민티스페이스 (D:\Sites\mintspace)

> 민티 전용 데스크탑 워크스페이스. 모든 프로젝트 폴더/문서/링크를 한 화면에서 관리 + 클릭 한 번에 열기.

## 구조

- **화면** (`web/`) = Vercel 정적 배포. `git push` 해야 화면 반영. 메모리 [[mintspace-vercel-frontend]] 참고.
- **API** (`helper/server.py`) = FastAPI 로컬 헬퍼. http://localhost:5500.
  - **기동**: `start.bat` 더블클릭 (또는 윈도우 시작프로그램에 등록돼 있어 부팅 시 자동). 콘솔 안 띄우려면 `pythonw` 로 띄움. 디버깅 땐 `python helper/server.py` (콘솔 로그 보임).
  - ⚠ **pythonw 로 띄우면 `sys.stdout` 이 `None`** → uvicorn 컬러 로깅의 `sys.stdout.isatty()` 에서 죽음(2026-05-30 발견). server.py 상단에서 stdout/stderr None 이면 `os.devnull` 로 채우는 가드로 해결. 이 가드 지우면 자동시작이 silent fail.
  - ⚠ 헬퍼 재시작 시 **절대 포트 강제 종료(`Stop-Process` on 5500) 금지**: 헬퍼가 launch-terminal 로 띄운 cldp 자식 터미널까지 연쇄 사망. 옛 `start-helper.ps1` 이 이 짓을 해서 제거함(2026-05-29). 안전 런처는 "이미 떠 있으면 재기동 안 함" 방식만. (단 cldp 자식이 0개면 그 python 만 단독 종료해도 안전.)
- **데이터** (`data/`) = `.gitignore`. 로컬 전용 (NAS 경로 등 민감).
  - `projects.json` (카테고리 + 큰 카드들 = 클로드 코드로 작업하는 프로젝트 + `groups` 탭 그룹)
  - `bookmarks.json` (미니카드 = 폴더/파일/링크 바로가기)
  - `token.txt`, `logs/YYYY-MM-DD.md`

## 현재 상태 (2026-06-22)

### 완료된 큰 기능

> 5월~6월초 기능 13개(바탕화면 수집/미니카드/카테고리/별표·즐겨찾기/줄바꿈 등)는 `docs/archive/2026-06-22-cleanup.md` 로 분리. 아래는 6월 중순 이후 최신 기능만.

- [x] **cldp 터미널 탭/새창 분기** (2026-06-13) - 카드 `💬 cldp` 버튼: **그냥 클릭 = `-w 0`**(가장 최근 wt 창에 탭으로) / **Shift+클릭 = `-w new`**(새 창 = 새 그룹). 프론트는 `e.shiftKey` → `new_window` 로 전달. 옛 `-w new` 매번 새 창에서 변경. pythonw 백그라운드는 foreground lock 때문에 탭 붙여도 작업표시줄만 깜빡임 → Popen 직전 `AllowSetForegroundWindow(-1)`(`_allow_foreground()`) 가드로 앞으로 올림. **동기**: 수동으로 탭을 드래그-합치다 창 전체가 종료되던 사고 방지 (처음부터 의도한 창에 탭으로 열어 합칠 일 자체를 없앰)
- [x] **탭 그룹 (워크스페이스)** (2026-06-13) - 자주 같이 여는 프로젝트를 묶어 **버튼 하나로 새 창 하나에 cldp 탭 좌르륵**. 직접 생성/편집/삭제, 멤버는 모달 체크박스로 넣다 뺐다, 여러 그룹 가능. `[▶ 전체 열기]` → `wt -w new` + 각 멤버 `new-tab` 을 `;`(wt 서브커맨드 구분자)로 이어붙여 한 창에 탭. 멤버 폴더 없으면 skip. WT 없으면 개별 새 콘솔 폴백. groups 는 `projects.json` 에 저장(로컬 전용, gitignore). 사이드바 nav `🗂 탭 그룹` + `#tab-groups` 섹션 + `#group-modal`. JS `renderGroups`/`renderGroupCard`/`openGroupModal`/`setupGroupModal`, 편집모드 연동(✕ 배지 + 열기 비활성). 모달에 **프로젝트 이름 검색창**(`grp-search`, 체크 상태 유지하며 필터) + "N개 선택됨" 힌트. ⚠ 모달 공통 `input{width:100%}` 이 체크박스까지 늘려 깨지므로 `.grp-check input[type=checkbox]` 16px 고정 필수
- [x] **작업 복원** (2026-06-13, 윈도우 48시간으로 확대 2026-06-14) - 상단바 `[🕐 작업 복원]` → `logs/*.md` 의 cldp launch 기록(`- HH:MM  💬 [pid] cldp`)을 정규식(`_LAUNCH_RE`) 파싱 → **마지막 launch 시각부터 48시간(2일) 윈도우 안에 연 프로젝트**(중복 제거, 최근순)를 후보로 → 체크 모달 → **새 창 하나에 탭으로 복원**. launch 코어는 그룹과 공유(`_open_projects_in_one_window`). 폴더 없는 후보는 disabled 흐림. 동기: 터미널 창 전체가 닫혔을 때 일일이 안 열고 한 번에 + 탭 그룹보다 여기서 이어갈 작업 고르는 게 편함. 개별 cldp(💬)만 추적(그룹 🗂 로그는 멤버 id 없어 제외). ⚠ 윈도우 늘릴 때 `_recent_launch_pids` 가 읽는 로그 파일 개수(`[:8]`)도 같이 봐야 함 — 자정 경계로 날짜가 여러 개 걸리고 작업 안 한 날은 파일이 없으므로 넉넉히 읽고 cutoff 로 거름
- [x] **폴더 작업 복원** (2026-06-19) - 상단바 `[📂 폴더 복원]` → cldp 작업 복원의 폴더판. `logs/*.md` 의 폴더 열기 기록(`- HH:MM  📂 [id] 폴더 열림`)을 `_FOLDER_RE` 로 파싱 → 마지막 세션 48시간 윈도우 후보 → 체크 모달 → **각각 탐색기로 열기**(cldp 와 달리 탭으로 못 묶음 — explorer 는 탭 제어 API 자체가 없음, 그래서 "폴더도 새 탭 기본" 요청은 기본 탐색기로 불가). id 규칙으로 큰 카드/미니카드 둘 다 매칭: open_folder 가 프로젝트는 `[p.id]`, 미니카드는 `[bm-{b.id}]` 로 찍음 → `bm-` 접두면 bookmarks, 아니면 projects 에서 `_resolve_folder_id`. 복원 실행 로그는 `🕐 폴더 복원: N개`(개별 `📂 폴더 열림` 과 다른 문구 → 다음 후보에 안 섞임). 서버 `_recent_folder_opens`/`/api/restore-folders`/`/api/restore-folders-launch`, 프론트 `openFolderRestoreModal`/`setupFolderRestore`(cldp 복원 함수 세트를 그대로 복제). ⚠ server.py 변경이라 헬퍼 재시작 필요
- [x] **작업/폴더 복원 기본값 = 전체 해제** (2026-06-22) - 두 복원 모달이 처음 뜰 때 후보가 다 체크돼 있던 걸 **전부 미선택**으로 변경. 렌더에서 `${c.exists ? "checked":""}` + `.grp-check.on` 제거(`openRestoreModal`/`openFolderRestoreModal`). 폴더 없는 후보 disabled 흐림은 유지. 힌트 `0 / N개 선택됨`으로 시작. 캐시 `?v=2026062101`
- [x] **헬퍼 보안 강화** (2026-06-22) - "사이트 노출 시 위협" 점검에서 구멍 발견·봉쇄. ① CORS `allow_origin_regex` 를 `*.vercel.app`/`*.pages.dev` 와일드카드(=누구나 만드는 사이트 통과) → `mintspace[a-z0-9-]*\.vercel\.app` + 로컬만으로 좁힘 ② `token-bootstrap` 이 `client.host==127.0.0.1` 만 보던 걸(악성 외부 페이지가 피해자 PC에서 localhost fetch 하면 TCP 소스가 127.0.0.1이라 통과 → 토큰 탈취) **Origin/Sec-Fetch-Site 검증** 추가로 cross-origin 차단. 실제 공격 흉내(`Origin: evil.vercel.app`, `Sec-Fetch-Site: cross-site`)로 403 검증 완료. 정상 로컬·내 vercel 배포는 통과. 상세 → 메모리 [[mintspace-helper-cors-token-hardening]]. ⚠ server.py 변경이라 헬퍼 재시작 필요

- [x] **프로젝트 카드 사이트 다중화** (2026-06-27) - 한 카드에 참조 사이트 여러 개(메인·관리자 등). 프로젝트마다 `sites: [{label, url}]` 배열로 저장(라벨 자유 입력, 비우면 카드 버튼이 "사이트"). 카드는 사이트마다 `🌐 {라벨}` 버튼 하나씩, 클릭 시 `data-idx`로 클로저의 `sites[i].url` 열기(이스케이프 회피). 추가/편집 모달은 단일 URL 칸 → "라벨+URL 행 여러 개 + [+ 사이트 추가]" (`renderSiteRows`/`collectSiteRows`/`siteRowHtml`, 삭제·추가는 `setupSiteRows` 이벤트 위임 1회 연결, 다 지우면 빈 행 1개 유지). 옛 단일 `url`은 get_projects 가 sites 로 자동 마이그레이션 + add/update 가 `url`=첫 사이트로 동기화(하위호환). 빈 행은 `collectSiteRows`/서버 양쪽에서 거름 → 다 비우면 sites=[] + url=null 로 🌐 버튼 사라짐. CSS `.site-row`(flex, `.site-label` 96px 고정 / `.site-url` flex:1 — 공통 `input{width:100%}` override). 캐시 `?v=2026062701`. ⚠ server.py(SiteLink 모델, ProjectIn/Patch, get_projects/add/update) 변경이라 헬퍼 재시작 필요

### 다음 할 것
- [ ] 탭 그룹: 카드에서 멤버 칩 X로 바로 빼기 + 그룹 순서 드래그 (지금은 편집 모달 체크박스로만)
- [ ] 바탕화면 스캔에 파일 포함 옵션 (지금은 폴더만 일괄 수집; 파일은 모달로 개별 추가)
- [ ] 즐겨찾기 섹션 카드도 드래그로 카테고리/순서 변경
- [ ] 카드 노트(메모) 편집 UI - 서버 PATCH note 는 이미 지원, 모달 UI 만 추가
- [ ] 카테고리 자체 순서 변경 (지금은 추가 순서대로 고정)
- [ ] 검색 결과에서 카테고리 헤더 보존 (일부 섹션이 숨겨질 수 있음)

## API 라우트 (helper/server.py)

- **프로젝트(큰 카드)**: GET `/api/projects` · POST/PATCH/DELETE `/api/projects-meta/{id}` · POST `/api/projects-order`
- **카테고리**: POST `/api/categories` · PATCH/DELETE `/api/categories/{id}`
- **바로가기(미니카드)**: GET/POST `/api/bookmarks` · PATCH/DELETE `/api/bookmarks/{id}` (PATCH 에 folder 도 지원 → type 재판별) · POST `/api/bookmarks-order` · POST `/api/bookmarks-import` (바탕화면 스캔) · POST `/api/bookmarks-rowbreak` (줄바꿈 라인)
- **액션**: POST `/api/open-folder` (폴더/파일 둘 다 `os.startfile`) · POST `/api/launch-terminal` (cldp, `new_window` true=새창/false=최근창 탭)
- **탭 그룹**: GET/POST `/api/groups` · PATCH/DELETE `/api/groups/{id}` · POST `/api/groups/{id}/launch` (멤버 전부 한 창에 탭으로)
- **작업 복원**: GET `/api/restore-candidates?window=2880` (마지막 세션 cldp 프로젝트, 기본 48시간) · POST `/api/restore-launch` (선택 id 들 한 창에 탭으로)
- **폴더 복원**: GET `/api/restore-folders?window=2880` (마지막 세션 연 폴더 = 큰 카드+미니카드) · POST `/api/restore-folders-launch` (선택 id 들 각각 탐색기로, 탭 X)
- **추천**: GET `/api/star-suggestions?days=7&threshold=5` (`helper/auto_star.py` logs 분석)
- **인증**: GET `/api/token-bootstrap` (로컬 IP + **로컬 Origin/Sec-Fetch 검증** 통과 시에만 자동 발급. 외부 페이지발 cross-origin 요청은 403)
- **헬스**: GET `/api/health`

## 주의

- 데이터 파일 `.gitignore` 이라 다른 PC / 배포에선 빈 상태로 보임 (NAS 경로 노출 방지 의도)
- 외부(Vercel) 접속 시엔 사이드바 ⚙ 설정에서 헬퍼 URL + 토큰 입력 필요
- 헬퍼 재시작 필요 시점: `server.py` / `desktop_scan.py` 변경 시. 정적 파일(html/js/css) 만 바뀌면 새로고침으로 충분
- **캐시 버스팅**: `web/index.html` 의 `?v=YYYYMMDDNN` 버전 안 올리면 브라우저가 옛 js/css 사용 (현재 `?v=2026062101`)
- **보안 (2026-06-22)**: 헬퍼는 127.0.0.1 바인딩이라 외부 직접 침입은 불가하나, 민티가 악성 외부 페이지를 열면 그 JS가 localhost 헬퍼를 조종할 수 있던 구멍을 막음. CORS 화이트리스트(`mintspace*.vercel.app`+로컬)와 token-bootstrap Origin 검증 **둘 중 하나라도 와일드카드/host-only 로 되돌리면 구멍 재발**. 상세 → [[mintspace-helper-cors-token-hardening]]
- bat 파일 직접 수정 금지 (CP949+CRLF 인코딩 필요. Python 으로 저장하거나 PowerShell 분리)
- ✅ **안전 start.bat 재구축 (2026-05-30)**: `start.bat` = health 체크 후 "이미 떠 있으면 재기동 안 함" + 강제 종료 절대 안 함 + `pythonw` 절대경로로 기동. 윈도우 시작프로그램(`시작 폴더\mintspace-helper.lnk`, 최소화)에 등록돼 **부팅 시 자동 기동**. 메모리 [[mintspace-helper-restart-footgun]] 참고
- **터미널 띄우기 (2026-06-13 갱신)**: `launch-terminal` 은 클릭=`-w 0`(최근 wt 창에 탭) / Shift+클릭=`-w new`(새 창). 탭 그룹은 `-w new` + `;` 로 한 창에 멀티탭. 옛날엔 `new-tab` 만 쓰면 깜빡이기만 했는데(포커스 안 옴), 그건 pythonw 백그라운드의 foreground lock 때문이었음 → `_allow_foreground()`(`AllowSetForegroundWindow(-1)`)로 해결. 이 가드 지우면 탭 모드에서 다시 작업표시줄만 깜빡임.

## 관련 메모리

- [[mintspace-vercel-frontend]] - Vercel 배포 구조 (화면 Vercel, API 로컬)
- [[mintspace-folder-shortcuts]] - 바로가기 시스템 운영 지식 (type 판별, 분류 규칙, gitignore)
- [[mintspace-helper-restart-footgun]] - 헬퍼 재시작 시 포트 강제 종료 금지 (자식 터미널 연쇄 사망)
- [[mintspace-helper-cors-token-hardening]] - CORS·token-bootstrap 보안 (와일드카드/host-only 로 되돌리면 악성 페이지가 토큰 탈취)
