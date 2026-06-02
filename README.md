# Epub Binder

Windows PyQt6 기반 EPUB/TXT 정리 도구입니다. 병합, 이름 변경, TXT 변환, EPUB 추출, 중복 정리를 한 창에서 처리합니다.

이 README는 Codex가 새 작업을 시작할 때 전체 폴더를 다시 훑지 않고 바로 진입점을 찾기 위한 작업 지도 역할도 합니다.

## 현재 버전

- 버전: `5.1.0`
- 메인 실행 진입점: `epub_binder4.3.4.py`
- 공개용 실행 진입점: `epub_binder5.1.0_public.py`
- 기본 빌드 스크립트: `epub_binder_bulid.bat`
- 오리지널 EXE: `EpubBinder5.1.0.exe`
- 공개용 EXE: `EpubBinder5.1.0_public.exe`
- 공개용 만료일: `2026-09-30`
- 사용자 설명서: `docs/USER_MANUAL.html`

## 주요 기능

- EPUB 병합
- 전체 권 표지 후보 선택
- 대표 표지 1개와 추가 표지 여러 개 삽입
- 병합 목차 미리보기와 제목 편집
- 파일명/OPF/목차 기반 이름 변경
- 이름 변경 결과 기준 ZIP 묶기
- TXT to EPUB 변환
- EPUB to TXT 추출
- 네이버 시리즈 표지 검색
- 중복 후보 정리, 삭제 후보 자동선택, 확인대상 해시 확인

## 최근 5.1.0 작업 포인트

- 외전, 번외, 특별외전, 특외를 같은 시리즈 묶음으로 인식한다.
- 자동 정렬은 본편 다음에 에필로그, 외전, 특별외전, 특전 순서를 기본으로 둔다.
- 단행본 병합 제목은 본편과 외전이 섞여도 전체 파일 수 기준 `1-n권`으로 잡는다.
- 외전만 있는 연재본은 `작품명 외전 1-57화`처럼 외전 회차 범위를 보존한다.
- 표지 후보는 권별 전환보다 전체 후보를 먼저 모아 보여준다.
- 표지 후보 창은 세로 스크롤을 사용한다.
- 유사 이미지 표지는 가능한 한 중복 후보를 줄여 보여준다.
- 추가 표지는 `표지 추가` 체크 순서대로 대표 표지 뒤에 들어간다.
- 병합이 끝나면 현재 파일 리스트를 비워 재병합 실수를 줄인다.
- 중복 정리에서 `1-1`, `1-2`, `상`, `중`, `하` 같은 정상 분권 표기는 삭제 후보로 묶지 않는다.
- 오리지널 빌드에는 만료일을 넣지 않고, 공개용 빌드에만 만료일과 7일 전 경고를 적용한다.

## 폴더 구조

```text
epub-binder/
  epub_binder4.3.4.py          메인 실행 진입점
  epub_binder5.1.0_public.py   공개용 실행 진입점
  epub_binder_bulid.bat        PyInstaller 빌드 스크립트
  AGENTS.md                    Codex 작업 규칙
  README.md                    빠른 작업 지도
  config/                      아이콘 등 빌드 자원
  docs/                        설명서, 프로젝트 지도, 리팩토링 기록
  epub_binder_app/             PyQt UI, 다이얼로그, 워커, 설정
  epub_binder_core/            EPUB/TXT/표지/중복 정리 순수 로직
  tests/                       pytest 회귀 테스트
```

생성물과 복구 부산물은 소스 변경으로 보지 않습니다.

```text
.venv/
build/
dist/
__pycache__/
.pytest_cache/
*.exe
*.spec
recovered_from_exe/
```

## 기능별 진입점

| 기능 | 먼저 볼 파일 | 관련 core |
|---|---|---|
| 병합 | `epub_binder_app/ui/main_window.py`, `epub_binder_app/workers.py` | `merge.py`, `merge_plan.py`, `toc.py`, `cover.py`, `epub_io.py` |
| 표지 후보 | `epub_binder_app/ui/dialogs.py`, `main_window.py` | `cover.py`, `naver_series.py` |
| 이름 변경 | `main_window.py` | `title_parser.py`, `title_metadata.py`, `rename_service.py`, `grouping.py` |
| ZIP 묶기 | `main_window.py` | `grouping.py`, `name_cleanup.py` |
| TXT to EPUB | `main_window.py` | `txt_parser.py`, `txt_detection.py`, `txt_chapters.py`, `txt_conversion.py`, `txt_epub.py` |
| EPUB to TXT | `main_window.py` | `epub_text.py` |
| 중복 정리 | `main_window.py` | `duplicate_cleanup.py`, `duplicate_service.py` |
| 네이버 시리즈 | `main_window.py`, `dialogs.py` | `naver_series.py`, `errors.py` |

## 작업 시작 체크리스트

1. `AGENTS.md`를 먼저 읽는다.
2. 이 `README.md`에서 기능별 진입점을 확인한다.
3. 관련 core 파일과 관련 테스트만 먼저 읽는다.
4. UI 변경이면 `epub_binder_app/ui/main_window.py`와 필요한 다이얼로그만 좁혀 본다.
5. 생성물 폴더, 복구 부산물, 대용량 테스트 원본은 요청이 있을 때만 본다.
6. 변경 후 최소 `compileall`을 실행하고, 가능하면 관련 pytest를 실행한다.

## 자주 쓰는 명령

문법 확인:

```powershell
python -m compileall -q epub_binder_app epub_binder_core epub_binder4.3.4.py epub_binder5.1.0_public.py
```

테스트:

```powershell
python -m pytest -q
```

오리지널 빌드:

```powershell
cmd /c "echo. | epub_binder_bulid.bat"
```

공개용 빌드 예시:

```powershell
cmd /c "call .venv\Scripts\activate.bat && python -m PyInstaller --noconfirm --clean --onefile --windowed --name EpubBinder5.1.0_public --icon=config\icon\app_icon.ico --add-data=config\icon\app_icon.ico;config/icon epub_binder5.1.0_public.py"
```

## 문서

- 사용자 설명서: `docs/USER_MANUAL.html`
- 프로젝트 지도 원본: `docs/CODEX_PROJECT_MAP.md`
- 개선/비용 메모: `docs/CODEX_IMPROVEMENT_AND_COST_REPORT.md`
- 리팩토링 기록: `docs/REFACTORING_TASKS.md`
- 최종 리팩토링 계획: `docs/FINAL_REFACTORING_PLAN.md`

설명서 캡쳐를 새로 넣을 때는 `docs/USER_MANUAL.html` 기준으로 갱신하고, 실제 개인 경로와 링크가 보이지 않게 확인합니다.

## Git 백업

- 원격: `https://github.com/remona192/epub-binder.git`
- 복구 브랜치: `recovery-5.1.0`
- 기본 방침: `main`에 바로 덮어쓰지 말고 복구/작업 브랜치에 먼저 백업한다.
- EXE, build, dist, `.venv`, 디컴파일 부산물은 커밋하지 않는다.

## 개발 메모

- 가능한 로직 변경은 `epub_binder_core/`에 두고 테스트를 붙인다.
- GUI 연결과 사용자 흐름은 `epub_binder_app/`에서 처리한다.
- `main_window.py`는 아직 크기 때문에 필요한 함수명으로 `rg`해서 좁혀 읽는다.
- EPUB 수정은 ZIP 구조, OPF 경로, manifest, spine, TOC 참조를 깨지 않게 한다.
- 네이버 시리즈 관련 테스트는 실시간 네트워크 대신 fixture와 mock을 우선 사용한다.
