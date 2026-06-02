# Codex Project Map

Last updated: 2026-05-27
Project: Epub Binder PyQt desktop app
Current target version: 4.3.4

이 문서는 Codex가 다음 작업에서 전체 폴더를 매번 훑지 않고, 필요한 지점으로 바로 들어가기 위한 지도다.
먼저 이 파일을 읽고, 관련 모듈과 테스트만 좁혀서 확인한다.

## 1. 빠른 결론

- 앱은 로컬 Windows PyQt6 데스크톱 앱이다.
- 현재 핵심 기능은 병합, 이름 변경, txt2epub, epub2txt, 중복 정리다.
- 순수 로직은 `epub_binder_core/`로 많이 분리되어 있다.
- 실제 UI와 일부 워커 구현은 아직 `epub_binder_app/ui/main_window.py`에 크게 남아 있다.
- 테스트는 `tests/`에 잘 쌓여 있으며, 최근 기준 전체 `pytest`는 206개 통과 상태였다.
- Vercel, Supabase는 현재 프로젝트에 직접 연결되어 있지 않다.
- GitHub도 아직 저장소가 아니며, 사용 시 큰 exe/빌드 산출물/테스트 원본 파일을 올리지 않는 것이 중요하다.

## 2. 작업 시작 체크리스트

1. `AGENTS.md`를 먼저 확인한다. 현재 파일은 인코딩이 깨져 보일 수 있으나 핵심 원칙은 다음과 같다.
2. 변경 전에는 가능하면 백업 또는 git 초기 커밋을 만든다.
3. 기능 로직은 먼저 `epub_binder_core/`에서 찾는다.
4. UI, 버튼, 탭, QThread 연결은 `epub_binder_app/ui/main_window.py`에서 찾는다.
5. 이미 분리된 워커는 `epub_binder_app/workers.py`에도 있으나, 실제 앱에서 여전히 `main_window.py` 내부 워커를 쓰는 부분이 있다.
6. 수정 후 기본 검증은 아래 명령을 우선 사용한다.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m compileall epub_binder_core epub_binder_app epub_binder4.3.4.py
```

빌드가 필요하면:

```powershell
cmd /c "echo. | epub_binder_bulid.bat"
```

## 3. 폴더 지도

```text
epub-binder/
  epub_binder4.3.4.py          앱 진입점
  epub_binder_bulid.bat        PyInstaller 빌드 스크립트
  EpubBinder4.3.4.spec         PyInstaller spec
  AGENTS.md                    작업 규칙
  docs/                        프로젝트 지도, 리팩터링 기록
  config/                      아이콘/빌드 관련 정적 자원
  epub_binder_core/            핵심 순수 로직
  epub_binder_app/             PyQt 앱, UI, 워커, 설정
  tests/                       pytest 회귀 테스트
  테스트/                      사용자가 직접 가져오는 실제 테스트 케이스
  중복정리/                    중복 정리 테스트/참고 파일
  보관_20260521/               이전 백업과 복구 자료
  build/, dist/                빌드 산출물
  .venv/, __pycache__/         로컬 실행/캐시 산출물
```

탐색 우선순위:

- 먼저 볼 곳: `epub_binder_core/`, `epub_binder_app/ui/main_window.py`, `tests/`
- 필요할 때만 볼 곳: `docs/`, `config/`, `테스트/`, `중복정리/`
- 보통 건드리지 않을 곳: `build/`, `dist/`, `.venv/`, `__pycache__/`, `.pytest_cache/`
- 역사 확인용: `보관_20260521/`

## 4. Core 모듈 지도

| 모듈 | 역할 | 주로 관련된 기능 |
|---|---|---|
| `title_parser.py` | 파일명에서 작가, 제목, 권수, 회차, 완결 여부 파싱 | 이름 변경, 중복 정리, 묶기 |
| `name_cleanup.py` | 언더바, 작가 중복, 숫자 범위 등 제목 정리 | txt2epub, 이름 변경 |
| `title_metadata.py` | EPUB 내부 OPF/HTML 제목/작가 후보 추출 | 이름 변경 |
| `rename_service.py` | 이름 변경 계획/결과 계산 | 이름 변경 |
| `grouping.py` | 같은 시리즈 묶음 키 계산 | 이름 변경, zip/7z 묶기 |
| `merge.py` | 단순 병합 서비스 | 병합 |
| `merge_plan.py` | 고급 병합 구조, OPF/NCX/TOC 생성 보조 | 병합 |
| `toc.py` | 목차 감지, 챕터 제목 추출, 병합 목차 제목 결정 | 병합, txt2epub 미리보기 |
| `cover.py` | 표지 추출/후보 수집 | 병합, 이름 변경, txt2epub |
| `epub_io.py` | EPUB zip/container/OPF/spine 읽기 | 병합, 이름 변경, epub2txt |
| `epub_cleanup.py` | 보이지 않는 문자 제거, 이미지 압축 등 | 병합, 이름 변경 |
| `epub_archive.py` | ZIP 내부 경로/타임스탬프/압축 안정화 | 병합, 정리 |
| `epub_text.py` | EPUB을 TXT로 추출 | epub2txt |
| `txt_parser.py` | TXT 인코딩/제목/작가 메타 추출 | txt2epub |
| `txt_detection.py` | TXT 챕터 시작점 감지 | txt2epub |
| `txt_chapters.py` | 챕터 목록 보정, 짧은 챕터 병합, 오탐 처리 | txt2epub |
| `txt_conversion.py` | TXT 변환 작업 단위 서비스 | txt2epub |
| `txt_epub.py` | TXT 챕터 목록을 EPUB으로 생성 | txt2epub |
| `naver_series.py` | 네이버 시리즈 표지/작가 가져오기 | txt2epub, 표지 검색 |
| `duplicate_cleanup.py` | 제목 기반 중복 후보 계산 | 중복 정리 |
| `duplicate_service.py` | 중복 정리 실행/해시 계산 보조 | 중복 정리 |
| `errors.py` | core 예외와 사용자 메시지 변환 | 전체 |

## 5. UI와 워커 지도

`epub_binder_app/ui/main_window.py`가 가장 크다. 작업할 때는 전체를 읽지 말고 아래 구간만 좁혀서 본다.

| 구간 | 대략 위치 | 역할 |
|---|---:|---|
| helper/import/fallback | 상단 ~ 4,800 | core 함수 연결, 공용 helper |
| 내부 Worker 클래스 | 약 4,800 ~ 6,700 | Scan/Strip/Merge/Txt/EpubTxt 워커 |
| 메인 UI 생성 | 약 7,000 ~ 7,200 | 탭 생성 |
| 병합 탭 | 약 7,150 ~ 7,430, 10,450 이후 | 병합 목록/옵션/실행 |
| 이름 변경 탭 | 약 7,420 ~ 9,650 | 이름 변경 UI와 적용 |
| txt2epub 탭 | 약 11,730 ~ 12,400 | TXT 추가, 감지, 미리보기, 변환 |
| epub2txt 탭 | 약 12,410 이후 | EPUB to TXT |
| 중복 정리 탭 | 약 12,650 이후 | 중복 후보 표시/이동 |
| TXT 미리보기 다이얼로그 | 약 13,250 이후 | 챕터 편집/오탐 병합 |
| 네이버 표지 다이얼로그 | 후반부 | 표지/작가 가져오기 |

`epub_binder_app/workers.py`에도 분리된 워커가 있다. 테스트나 리팩터링 대상이다.
단, 실제 앱 실행 경로가 어느 워커를 쓰는지 항상 확인한다.

## 6. 기능별 진입점

### 병합

- UI: `epub_binder_app/ui/main_window.py`
- 핵심 워커: `MergeWorker`
- core: `merge_plan.py`, `toc.py`, `cover.py`, `epub_io.py`, `epub_archive.py`
- 주요 테스트: `tests/test_merge.py`, `tests/test_merge_plan.py`, `tests/test_advanced_merge_legacy.py`, `tests/test_toc_helpers.py`

최근 주의점:

- 병합 목차 제목은 `toc.merge_page_title_from_sources()`를 우선 확인한다.
- 이름 변경과 병합은 제목을 얻는 경로가 다르다.
- 이름 변경은 파일명/메타 중심이고, 병합은 EPUB 내부 NCX/HTML 페이지 제목 중심이다.

### 이름 변경

- UI: `main_window.py`의 `_build_rename_tab`, `_rename_extract`, `_rename_apply`
- core: `title_parser.py`, `title_metadata.py`, `rename_service.py`, `grouping.py`, `name_cleanup.py`
- 주요 테스트: `tests/test_title_parser.py`, `tests/test_rename_service.py`, `tests/test_title_metadata.py`, `tests/test_grouping.py`

### txt2epub

- UI: `main_window.py`의 `_build_txt_tab`, `_txt_detect`, `_txt_open_preview`, `_txt_start_convert`
- core: `txt_parser.py`, `txt_detection.py`, `txt_chapters.py`, `txt_conversion.py`, `txt_epub.py`, `name_cleanup.py`
- 주요 테스트: `tests/test_txt_conversion.py`, `tests/test_txt_conversion_service.py`, `tests/test_txt_detection.py`, `tests/test_txt_chapters.py`, `tests/test_txt_edge_cases_431.py`

### epub2txt

- UI: `main_window.py`의 `_build_epub2txt_tab`
- core: `epub_text.py`
- 주요 테스트: `tests/test_epub_text.py`, `tests/test_epub_text_service.py`

### 네이버 시리즈 표지

- UI: `main_window.py`, `ui/dialogs.py`
- worker: `NaverSeriesFetchThread`
- core: `naver_series.py`, `errors.py`
- 주요 테스트: `tests/test_naver_series.py`, `tests/test_core_errors.py`

주의:

- 네트워크 의존 테스트는 mock client로 유지한다.
- 실시간 네이버 호출을 자동 테스트에 넣지 않는다.

### 중복 정리

- UI: `main_window.py`의 `_build_dedupe_tab`
- core: `duplicate_cleanup.py`, `duplicate_service.py`, `title_parser.py`
- 주요 테스트: `tests/test_duplicate_cleanup.py`

현재 설계 방향:

- 제목이 거의 같은 후보만 묶는다.
- 권수/시즌/회차 범위가 다르면 다른 파일로 보는 쪽이 안전하다.
- 해시 비교는 후보가 좁혀진 뒤 선택적으로 사용한다.

## 7. 테스트 지도

| 테스트 파일 | 담당 영역 |
|---|---|
| `test_toc_helpers.py` | 목차/챕터 제목 추출 |
| `test_advanced_merge_legacy.py` | 고급 병합 회귀 |
| `test_merge_plan.py` | OPF/NCX/TOC 병합 계획 |
| `test_title_parser.py` | 파일명 파싱 |
| `test_rename_service.py` | 이름 변경 계획 |
| `test_txt_chapters.py` | TXT 챕터 보정 |
| `test_txt_detection.py` | TXT 목차 감지 |
| `test_txt_conversion.py` | TXT 메타/변환 |
| `test_epub_text.py` | EPUB to TXT |
| `test_naver_series.py` | 네이버 표지 parser/client |
| `test_duplicate_cleanup.py` | 중복 정리 판단 |
| `test_app_package_smoke.py` | 앱 import smoke |

## 8. Codex로 개선 가능한 것

### 우선순위 높음

1. `main_window.py` 추가 분리
   - 탭별 파일로 나누면 실수와 토큰 소모가 크게 줄어든다.
   - 후보: `ui/tabs/merge_tab.py`, `rename_tab.py`, `txt_tab.py`, `epub_text_tab.py`, `dedupe_tab.py`

2. 실제 앱 Worker와 `workers.py` Worker 통합
   - 현재 일부 로직이 두 곳에 남아 있어 테스트 경로와 실제 실행 경로가 어긋날 수 있다.
   - 먼저 병합 목차처럼 core 함수로 공용화한 뒤, 최종적으로 한쪽을 제거한다.

3. 프로젝트 지도 유지
   - 기능을 크게 바꿀 때마다 이 문서의 "기능별 진입점"과 "테스트 지도"를 갱신한다.
   - 다음 Codex 작업은 이 문서부터 읽도록 한다.

4. fixture 기반 회귀 테스트 확장
   - 사용자가 통과/실패를 준 실제 파일 케이스를 최소 입력으로 줄여 fixture화한다.
   - 원본 전체를 저장하기보다 문제 패턴만 남긴 작은 TXT/EPUB를 만든다.

5. 중복 정리 안전장치 강화
   - "정리 후보"는 실제 삭제가 아니라 이동으로 유지한다.
   - 권/시즌/부/외전이 다른 경우는 강하게 분리한다.
   - 해시 비교 옵션은 후보 축소 후에만 수행한다.

### 우선순위 중간

1. 빌드 산출물 정리 자동화
   - `build/`, `dist/`, 루트 exe, spec, 임시 파일을 명확히 분류한다.
   - 배포용 exe만 남기는 정리 스크립트를 만든다.

2. UI 미리보기 품질 개선
   - 중복 정리, TXT 챕터 미리보기, 병합 목차 편집에서 색 대비와 컬럼 폭을 더 안정화한다.

3. 네이버 시리즈 회차 제목 매칭 연구
   - 네이버 회차 목록의 화수/소제목을 TXT 챕터와 매칭하는 기능은 가능하다.
   - 다만 로그인/페이지 구조 변경/유료 회차/웹 제한 때문에 구현 난이도와 유지보수 비용이 높다.
   - 먼저 parser만 mock fixture로 연구하는 것이 안전하다.

4. 성능 측정
   - 중복 정리의 제목 유사도, 해시 계산, 폴더 스캔 시간을 샘플 폴더 기준으로 로그화한다.
   - 큰 파일 해시는 lazy/옵션 처리한다.

### 우선순위 낮음

1. GitHub Actions CI
   - 저장소가 생긴 뒤 `pytest`와 `compileall`만 먼저 자동화한다.
   - exe 빌드는 로컬 수동 빌드가 더 안전하다.

2. 릴리즈 자동화
   - GitHub Releases에 exe를 올릴 수 있지만, 초기에는 수동 업로드를 권장한다.

## 9. Vercel, GitHub, Supabase 비용/부하 리스크

현재 앱은 로컬 데스크톱 앱이라 Vercel과 Supabase가 필요 없다.
GitHub도 아직 로컬 폴더가 저장소가 아니므로 비용은 발생하지 않는다.

### Vercel

현재 사용 여부: 사용 안 함.

유료 플랜을 부를 수 있는 경우:

- 웹판 데모를 Vercel에 올리고 큰 파일 업로드/다운로드를 처리하는 경우
- 서버리스 함수로 EPUB 변환/이미지 압축/중복 해시 계산을 돌리는 경우
- 대용량 exe나 EPUB 샘플을 Vercel 정적 파일로 배포하는 경우
- 이미지 최적화 기능으로 표지 이미지를 대량 처리하는 경우
- 봇이나 자동 테스트가 배포 URL을 반복 호출하는 경우

권장:

- 이 프로젝트에는 Vercel을 쓰지 않는다.
- 문서 사이트가 필요하면 정적 문서만 올리고, exe/샘플 파일은 올리지 않는다.

### GitHub

현재 사용 여부: 아직 git 저장소 아님.

유료/제한 리스크:

- private repository에서 GitHub Actions를 자주 돌리면 Actions minutes를 소비한다.
- PyInstaller 빌드를 Actions에서 돌리면 시간이 길고 캐시/아티팩트가 커진다.
- exe, build, dist, 대용량 테스트 파일을 커밋하면 저장소가 급격히 커진다.
- Git LFS를 쓰면 LFS 저장공간/트래픽 제한에 걸릴 수 있다.
- Actions artifact와 release asset을 많이 남기면 저장공간 관리가 필요하다.

권장:

- `.gitignore`에 `build/`, `dist/`, `*.exe`, `.venv/`, `__pycache__/`, `.pytest_cache/`, 대용량 테스트 원본을 유지한다.
- GitHub에는 소스, 작은 fixture, 문서만 올린다.
- CI는 처음에는 `pytest -q`와 `compileall`만 돌린다.
- exe 빌드는 로컬에서 하고, 정말 필요할 때만 Release에 업로드한다.

### Supabase

현재 사용 여부: 사용 안 함.

유료 플랜을 부를 수 있는 경우:

- 사용자별 변환 기록, 파일 목록, 표지 캐시를 Supabase DB에 저장하는 경우
- EPUB/TXT/표지를 Supabase Storage에 저장하는 경우
- 대용량 파일 다운로드/공유로 egress가 늘어나는 경우
- Realtime 기능으로 진행률/로그를 동기화하는 경우
- Edge Functions에서 변환/해시/압축을 돌리는 경우

권장:

- 이 앱은 로컬 파일 처리 앱이므로 Supabase를 붙이지 않는다.
- 백업/동기화가 필요해도 처음에는 로컬 JSON 설정과 수동 백업으로 충분하다.

## 10. 토큰 절약 작업법

다음 Codex 작업에서는 아래 순서를 따른다.

1. 이 문서를 먼저 읽는다.
2. 사용자가 말한 기능명을 "기능별 진입점"에서 찾는다.
3. 관련 core 파일 1~3개와 관련 테스트만 읽는다.
4. `main_window.py`는 관련 함수명으로 `rg`해서 그 구간만 읽는다.
5. 전체 폴더 목록은 필요할 때만 `rg --files`로 좁혀서 본다.
6. `보관_`, `build`, `dist`, `.venv`는 사용자가 복구/빌드/정리를 요청한 경우에만 본다.

추천 검색 예시:

```powershell
rg -n "merge_page_title|extract_chapter_title|TocEditDialog" epub_binder_core epub_binder_app tests
rg -n "_build_dedupe_tab|duplicate_cleanup|Duplicate" epub_binder_core epub_binder_app tests
rg -n "_txt_detect|detect_chapters|merge_short_chapters" epub_binder_core epub_binder_app tests
rg -n "_rename_extract|parse_epub_name|series_zip_key" epub_binder_core epub_binder_app tests
```

## 11. 다음 개선 후보

1. `main_window.py` 탭별 분리 계획을 별도 문서로 만든다.
2. 실제 앱에서 쓰는 Worker와 `epub_binder_app/workers.py`의 차이를 표로 비교한다.
3. 중복 정리 탭의 판단 로직을 "후보 탐색 -> 안전 필터 -> 선택적 해시 -> 이동 실행" 단계로 문서화한다.
4. 사용자 실제 테스트 케이스 중 실패 패턴만 작은 fixture로 축소한다.
5. Git 초기화 전에 현재 상태를 압축 백업하거나, 첫 커밋 기준선을 만든다.
