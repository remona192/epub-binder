# 리팩토링 실행 트래커

## 목적

이 문서는 `FINAL_REFACTORING_PLAN.md`를 실제 작업 단위로 쪼갠 실행 체크리스트다.

- `FINAL_REFACTORING_PLAN.md`: 전체 방향과 원칙
- `REFACTORING_TASKS.md`: Codex가 다음 작업을 고를 때 보는 실행 목록
- `AGENTS.md`: 작업 규칙과 에이전트 선택 기준

## 실행 규칙

- 항상 `AGENTS.md`를 먼저 따른다.
- 기존 동작을 보존한다.
- 새 제품 기능을 추가하지 않는다.
- 막히지 않았으면 사용자에게 다음 작업을 묻지 않는다.
- 이 파일의 첫 번째 미완료 항목부터 이어서 진행한다.
- 한 번 실행할 때 가능하면 미완료 항목 3개 이상을 끝낸다.
- 의미 있는 변경 뒤에는 테스트를 실행한다.
- 작업이 끝나면 이 파일의 체크박스와 작업 로그를 갱신한다.

중단 조건:

1. 테스트가 3회 실패하고 안전하게 고칠 수 없다.
2. 현재 코드가 `FINAL_REFACTORING_PLAN.md`와 충돌한다.
3. 작업이 기능 변경을 요구한다.
4. 작업이 큰 레거시 흐름 삭제를 요구한다.
5. 필요한 파일이나 fixture가 없다.

## 표준 검증 명령

```powershell
python -m pytest -q
python -m compileall -q epub_binder4.2.4.py epub_binder_core tests epub_binder_app
```

## 현재 상태

- 현재 단계: Phase 11 main_window legacy helper 축소 진행 중
- 다음 작업: 빌드 산출물 실행 확인 또는 다음 리팩토링 Phase 선정
- Last Verified / 마지막 검증일: 2026-05-27

마지막 검증 결과:

- `.\.venv\Scripts\python.exe -m pytest -q`: 215 passed
- `.\.venv\Scripts\python.exe -m compileall -q epub_binder_core epub_binder_app epub_binder4.3.4.py`: passed
- `cmd /c "echo. | epub_binder_bulid.bat"`: built `dist\EpubBinder4.3.4.exe` and root copy

## Phase 11. main_window legacy helper 축소

목표: `main_window.py`에 남은 과거 helper/fallback 구현을 실제 실행 경로에서 배제하고, core/app 패키지의 공통 함수로 수렴한다.

- [x] 병합 계속 안내문 제거를 `epub_binder_core.toc.remove_continued_notice_html`로 공통화한다.
- [x] `main_window.py`의 TOC helper 이름이 core 구현을 직접 사용하도록 연결한다.
- [x] smoke 테스트가 `main_window.py` TOC helper와 core 함수 identity를 검증한다.
- [x] `main_window.py`에 남은 legacy TOC fallback 본문을 삭제하거나 별도 compatibility 모듈로 이동한다.
- [x] 동일 구현인 `ScanWorker`를 `epub_binder_app.workers` 공통 클래스로 수렴한다.
- [x] `StripOnlyWorker`를 `epub_binder_app.workers` 공통 클래스로 수렴한다.
- [x] `TxtEpubWorker`와 `EpubTxtWorker`를 `epub_binder_app.workers` 공통 클래스로 수렴한다.
- [x] 네이버 표지 fetch 스레드를 `epub_binder_app.workers.NaverSeriesFetchThread` 공통 클래스로 수렴한다.
- [x] 남은 worker 클래스 크기와 method/signal 구성을 비교해 직접 수렴 위험도를 확인한다.
- [x] `main_window.py`의 TXT EPUB 빌드 helper를 `epub_binder_core.txt_epub.build_txt_epub`로 수렴한다.
- [x] `main_window.py` 내부 `MergeWorker`와 `epub_binder_app.workers.MergeWorker`의 차이를 비교하고 한쪽으로 수렴한다.
- [x] `main_window.py` 탭별 UI 코드를 `ui/tabs/` 하위 모듈로 나누는 계획을 갱신한다.
- [x] 동일 구현인 `FileListWidget`과 `CoverPickerDialog`를 기존 `ui/widgets.py`, `ui/dialogs.py` 모듈로 수렴한다.

탭 분리 계획:

- 1차: 순수 계산/파일 작업이 이미 core/app worker로 이동한 탭부터 분리한다. 대상은 `ui/tabs/text_tools.py`의 TXT EPUB/EPUB TXT 연결부와 `ui/tabs/cleanup_tab.py`의 중복 정리 연결부다.
- 2차: 병합 탭은 `MergeWorker` 공통화가 끝난 뒤 위젯 생성과 이벤트 연결만 별도 모듈로 이동한다. 병합 알고리즘은 `workers.py`와 `epub_binder_core`에 유지한다.
- 3차: 이름변경/ZIP 묶기 탭은 `rename_service`, `grouping` 호출부를 먼저 얇게 만든 뒤 분리한다.
- 각 단계는 UI 문구와 사용자-visible 동작을 바꾸지 않고, smoke 테스트로 main window import와 탭 등록 문자열을 고정한다.

완료 기준:

- 실제 앱 실행 경로가 core/app 공통 함수를 우선 사용한다.
- `main_window.py`에 도메인 정규식과 EPUB 목차 로직이 새로 늘어나지 않는다.
- 전체 테스트와 compileall이 통과한다.

## Phase 0. 기준 동작 고정

- [x] 기준 pytest 실행
- [x] 기준 compileall 실행
- [x] 레거시 파일 `py_compile` 실행
- [x] NCX `navPoint` attribute quoting 테스트 추가
- [x] OPF title과 HTML heading 우선순위를 함께 검증하는 이름변경 fixture 추가
- [x] `1-1`, `1-2`, `1-1.` 같은 같은 시리즈 zip 묶기 fixture 추가
- [x] TXT 챕터 정규화 fixture 추가
- [x] 네이버 시리즈 상세 영역 작가 추출 fixture 추가

## Phase 1. Core Wrapper 정리

목표: 레거시 공개 함수명은 유지하되 실제 구현은 `epub_binder_core`로 위임한다.

- [x] `remove_invisible_chars`가 core 구현을 호출한다.
- [x] `scan_invisible_chars`가 core 구현을 호출한다.
- [x] `strip_epub_in_memory`가 core 구현을 호출한다.
- [x] `add_noise_to_epub`가 core 구현을 호출한다.
- [x] `compress_epub_images`가 core 구현을 호출한다.
- [x] `apply_epub_timestamp`가 core 구현을 호출한다.
- [x] `extract_cover_image`가 core 구현을 호출한다.
- [x] `extract_cover_candidates`가 core 구현을 호출한다.
- [x] wrapper parity 테스트를 나머지 wrapper까지 확대한다. 현재 `scan_invisible_chars`, `apply_epub_timestamp` 중심으로만 검증된다.

완료 기준:

- 레거시 함수명은 유지된다.
- GUI/worker 호출부는 바꾸지 않는다.
- 실제 로직은 core에만 둔다.
- 관련 테스트가 통과한다.

## Phase 2. 이름변경과 Zip 묶기 분리

목표: 이름변경과 묶기 판단을 core로 옮기고 UI는 표시와 실행만 담당한다.

- [x] 파일명 파싱 fixture 추가
- [x] OPF title/creator 활용 fixture 추가
- [x] HTML heading 기반 제목 추출 fixture 추가
- [x] 중복 권수 제거 fixture 추가
- [x] 단일 파일 zip 제외 fixture 추가
- [x] 같은 시리즈 zip grouping key fixture 추가
- [x] `grouping.py`에 시리즈 묶기 계산 로직 추가
- [x] `RenameBatchDialog`가 core 계산 결과만 표시하도록 정리한다. 현재 core 우선 사용 후 레거시 fallback이 남아 있다.
- [x] zip 묶기 UI가 `build_series_groups`를 우선 사용한다.
- [x] zip 묶기 레거시 fallback을 제거할 수 있을 만큼 parity 테스트를 보강한다.

완료 기준:

- 이름변경 규칙은 `title_parser.py` 또는 grouping 계열 core 모듈에 둔다.
- UI는 core 결과를 표시하고 파일 작업만 수행한다.
- 같은 입력에 대한 이름과 묶기 key가 테스트로 고정된다.

## Phase 3. 목차와 병합 분리

목표: EPUB 병합/목차/표지 제거처럼 위험한 구조 조작을 작은 core helper로 분리한다.

- [x] 권목차 활성화 fixture 추가
- [x] 권목차 비활성화 fixture 추가
- [x] 권표지 활성화/보존 관련 fixture 추가
- [x] 권표지 비활성화/불필요 이미지 pruning fixture 추가
- [x] OPF manifest/spine 참조 무결성 테스트 추가
- [x] NCX label/navPoint 생성 테스트 추가
- [x] skip page 판단을 core helper로 이동한다. 현재 `toc.py`와 `merge_plan.py`가 담당한다.
- [x] NCX nav tree builder 추출
- [x] TOC HTML builder 추출
- [x] 고급 레거시 병합 동작을 유지하는 회귀 테스트 추가
- [x] `MergeWorker` 내부의 남은 병합 orchestration을 더 얇은 adapter로 줄인다.

완료 기준:

- 병합 결과의 OPF, NCX, spine, cover 참조가 테스트로 고정된다.
- 고급 레거시 병합 경로는 결과 변경 없이 core helper를 사용한다.

## Phase 4. TXT 변환 분리

목표: TXT 파싱과 EPUB 생성을 core에 두고 worker는 진행 상태와 파일 저장만 담당한다.

- [x] `detect_chapters`를 core로 이동
- [x] `filter_ascending_chapters`를 core로 이동
- [x] `fill_numeric_gaps`를 core로 이동
- [x] `merge_short_chapters`를 core로 이동
- [x] `normalize_chapter_style`를 core로 이동
- [x] `build_txt_epub`를 core로 이동
- [x] TXT 인코딩/메타데이터 파싱을 `txt_parser.py`로 분리
- [x] TXT 챕터 탐지를 `txt_detection.py`로 분리
- [x] TXT 챕터 후처리를 `txt_chapters.py`로 분리
- [x] TXT EPUB 생성을 `txt_epub.py`로 분리
- [x] 레거시 TXT wrapper와 core 결과 일치 테스트 추가
- [x] `TxtEpubWorker`를 progress emit과 core 호출 중심으로 더 줄인다.

완료 기준:

- TXT 관련 도메인 규칙은 core 모듈에 있다.
- `TxtEpubWorker`는 UI thread 작업, progress, 저장만 담당한다.

## Phase 5. EPUB 텍스트 추출 분리

목표: EPUB-to-TXT 로직을 `epub_text.py`에 둔다.

- [x] `extract_epub_text_sections`를 core로 이동
- [x] `_html_to_plain_text`에 해당하는 로직을 `html_to_plain_text`로 core 이동
- [x] `_cleanup_txt_text`에 해당하는 로직을 `cleanup_txt_text`로 core 이동
- [x] `_apply_txt_paragraph_indent`에 해당하는 로직을 `apply_txt_paragraph_indent`로 core 이동
- [x] EPUB text extraction 테스트 추가
- [x] `EpubTxtWorker`를 파일 선택, progress, 저장 중심으로 더 줄인다.

완료 기준:

- EPUB HTML 읽기와 TXT 섹션 구성은 `epub_text.py`가 담당한다.
- worker는 core 결과를 받아 저장하고 상태를 표시한다.

## Phase 6. 네이버 시리즈 분리

목표: HTML 파싱과 client 동작은 `naver_series.py`에 두고 UI thread는 쿠키/productNo/progress만 담당한다.

- [x] `parse_product_no` 직접 단위 테스트 추가
- [x] 상세 페이지 작가 추출 fixture 추가
- [x] `originalProductId` legacy pattern 테스트 추가
- [x] 표지 URL 후보 parser 테스트 추가
- [x] 회차 번호 선택 우선순위 테스트 추가
- [x] mock client 기반 fetch 테스트 추가
- [x] `NaverSeriesFetchThread`가 core fetch를 우선 호출한다.
- [x] `NaverSeriesFetchThread` 안에 남은 legacy parser/download fallback을 제거하거나 adapter로 격리한다.
- [x] UI thread 책임을 쿠키, productNo, progress message로만 줄인다.

완료 기준:

- HTML 파싱은 `naver_series.py`에만 둔다.
- 네트워크 없는 parser 테스트와 mock 기반 client 테스트가 분리되어 있다.
- UI thread에는 도메인 파싱 정규식이 남지 않는다.

## Phase 7. 결과와 예외 타입 정리

목표: core API 결과와 실패 표현을 예측 가능하게 만든다.

- [x] `CoreError` 추가
- [x] `InvalidEpubError` 추가
- [x] `MissingMetadataError` 추가
- [x] `CoverNotFoundError` 추가
- [x] `NaverFetchError` 추가
- [x] 일부 core API에 dataclass result type 도입. 예: `MergeResult`, `StripResult`, `NaverSeriesFetchResult`
- [x] tuple/dict 반환 API 중 외부 호출이 많은 부분부터 dataclass result로 전환한다.
- [x] worker-level exception handling을 사용자 메시지 변환 계층으로 정리한다.

완료 기준:

- core는 의미 있는 예외와 result type을 반환한다.
- worker는 core 실패를 사용자 메시지로 변환한다.
- core는 PyQt widget, signal, `QMessageBox`를 import하지 않는다.

## Phase 8. Legacy GUI 파일 물리 분리

목표: Phase 0-7에서 core 책임 분리가 끝난 상태를 유지하면서, 과거 단일 진입점의 GUI/worker/settings 코드를 물리적으로 나눠 파일 크기와 충돌 위험을 줄인다.

주의:

- 이 단계도 기능 변경이 아니다.
- 먼저 import 가능한 얇은 패키지 구조를 만들고, 한 번에 한 책임만 옮긴다.
- 당시의 legacy 진입점은 바로 삭제하지 않고 호환 facade 또는 legacy entry로 남긴다.
- 현재 진입점과 PyInstaller 빌드가 깨지지 않아야 한다.

- [x] `epub_binder_app/` 패키지와 `epub_binder_app/ui/` 하위 패키지 골격을 만든다.
- [x] 색상, 만료일, 기본 폰트, QSettings key 같은 설정성 상수를 `epub_binder_app/settings.py`로 분리한다.
- [x] `ScanWorker`, `StripOnlyWorker`, `MergeWorker`, `TxtEpubWorker`, `EpubTxtWorker`, `NaverSeriesFetchThread`를 `epub_binder_app/workers.py`로 옮긴다.
- [x] `FileListWidget`과 재사용 UI helper를 `epub_binder_app/ui/widgets.py`로 옮긴다.
- [x] `TxtPreviewDialog`, `RenameBatchDialog`, `TocEditDialog`, `CoverPickerDialog`, `NaverSeriesCoverDialog`를 `epub_binder_app/ui/dialogs.py` 또는 개별 dialog 모듈로 옮긴다.
- [x] `EPUBMergerGUI`를 `epub_binder_app/ui/main_window.py`로 옮긴다.
- [x] legacy 진입점을 기존 import/call 경로가 깨지지 않는 compatibility facade로 줄인다.
- [x] legacy 진입점이 새 app 패키지를 직접 로드하거나 facade를 통해 안정적으로 로드하도록 정리한다.
- [x] `epub_binder_bulid.bat`의 PyInstaller hidden-import/add-data 구성이 새 패키지 구조를 포함하는지 확인한다.
- [x] 새 패키지 import smoke 테스트를 추가한다.
- [x] GUI를 띄우지 않는 범위에서 worker/dialog import 테스트를 추가한다.
- [x] 표준 검증 명령 3개를 모두 통과시킨다.

완료 기준:

- 단일 진입점의 물리적 크기가 크게 줄어든다.
- 기존 실행 명령 `python epub_binder4.2.4.py`가 유지된다.
- 기존 테스트와 smoke import 테스트가 통과한다.
- core 책임 분리 방향을 되돌리지 않는다.

## Phase 9. Legacy helper/adapter 축소

목표: Phase 8 이후에도 legacy 진입점에 남아 있는 helper/wrapper/adapter 함수를 성격별 app/core 모듈로 옮겨, legacy 파일을 compatibility facade에 더 가깝게 줄인다.

주의:

- 이 단계도 기능 변경이 아니다.
- legacy 진입점의 기존 함수명은 당장 제거하지 말고 re-export 또는 얇은 wrapper로 유지한다.
- helper 이동 전후 결과가 같은지 parity 테스트를 먼저 추가한다.
- `epub_binder_app.ui.main_window.configure_main_window_dependencies`와 `epub_binder_app.workers.configure_worker_dependencies`의 주입 목록도 함께 정리한다.

- [x] 남은 top-level helper를 분류한다. 예: `natural_sort_key`, `human_size`, `_safe_title`, title 추출, TOC label, TXT wrapper, EPUB text wrapper, core dependency adapter.
- [x] `natural_sort_key`, `human_size`, `_safe_title`, 버튼/라벨 helper처럼 UI/표시 성격의 함수는 `epub_binder_app/ui/helpers.py` 또는 `epub_binder_app/utils.py`로 옮긴다.
- [x] `_read_dc_tag`, `_extract_creator_from_html`, `_extract_title_from_html`, `_normalize_title`, `_clean_opf_series_title`, `_find_series_volume_heading_in_zip` 계열은 core title/epub metadata helper로 옮기거나 기존 core API로 대체한다.
- [x] `_toc_label_from_filename`, `_prefer_filename_toc_title`, `_toc_episode_no`, subheading/anchor helper 계열은 `epub_binder_core/toc.py` 또는 `merge_plan.py`로 옮긴다.
- [x] `is_skip_page`, `extract_chapter_title`, `extract_all_subheadings`, `inject_subheading_anchors`의 legacy/core 중복을 정리하고 parity 테스트를 추가한다.
- [x] TXT wrapper 함수(`_decode_txt_bytes`, `detect_chapters`, `normalize_chapter_style`, `build_txt_epub` 등)를 legacy facade re-export 수준으로 줄인다.
- [x] EPUB text wrapper 함수(`_html_to_plain_text`, `_cleanup_txt_text`, `_apply_txt_paragraph_indent`, `extract_epub_text_sections`)를 legacy facade re-export 수준으로 줄인다.
- [x] `configure_worker_dependencies`와 `configure_main_window_dependencies`에 넘기는 `_core_*` 주입 목록을 최소화한다.
- [x] legacy 진입점에 남아야 하는 항목을 `QApplication`, `EPUBMergerGUI`, compatibility 함수명, 설정 bootstrap 정도로 제한한다.
- [x] legacy facade import smoke 테스트와 helper parity 테스트를 보강한다.
- [x] 표준 검증 명령 3개를 모두 통과시킨다.

완료 기준:

- legacy 진입점은 새 app/core 모듈을 재노출하는 facade에 가깝게 남는다.
- helper의 실제 구현 위치가 app/core 중 하나로 명확해진다.
- dependency injection adapter가 거대한 전역 주입 목록에 의존하지 않는다.
- 기존 GUI 실행 경로와 테스트 결과가 유지된다.

## Phase 10. Legacy facade 제거 및 4.2.4 진입점 확정

목표: `epub_binder4.2.4.py`만 최상위 실행 파일로 남기고, 호환 facade와 동적 로더를 제거한다.

- [x] `epub_binder4.2.4.py`가 `epub_binder_app.ui.main_window.EPUBMergerGUI`를 직접 실행하도록 바꾼다.
- [x] `epub_binder_app.ui.main_window`가 facade 주입 없이 필요한 core rename/grouping/metadata/toc 함수를 직접 import한다.
- [x] worker/dialog/widget의 legacy dependency configure adapter를 제거한다.
- [x] `epub_binder_bulid.bat`가 `epub_binder4.2.4.py`를 빌드 진입점으로 사용하고, 생성된 spec 파일은 남기지 않는다.
- [x] legacy facade re-export/parity 테스트를 core/app 직접 검증으로 바꾼다.
- [x] obsolete 진입점 파일명을 제거하고 `epub_binder4.2.4.py`를 현재 진입점으로 확정한다.
- [x] 표준 검증 명령을 `epub_binder4.2.4.py`, `epub_binder_core`, `epub_binder_app`, `tests` 기준으로 갱신한다.

완료 기준:

- 최상위 실행 파일은 `epub_binder4.2.4.py` 하나만 남는다.
- 앱 실행과 PyInstaller 빌드는 app/core 패키지를 직접 사용한다.
- 테스트에는 삭제된 facade 파일을 동적으로 로드하는 경로가 없다.
- 문서와 AGENTS 지침이 현재 구조를 설명한다.

## 작업 로그

### 2026-05-05

완료:

- 진입점의 동적 로더를 제거하고 app 패키지 직접 실행으로 전환했다.
- `epub_binder_app.ui.main_window`가 rename/grouping/metadata/toc core 함수를 직접 import하도록 정리했다.
- worker/dialog/widget의 legacy dependency configure adapter를 제거했다.
- build script에서 legacy facade add-data 구성을 제거하고 runtime 아이콘 data만 포함하도록 바꿨다.
- 생성물인 `EpubBinder4.2.4.spec`는 삭제했다.
- legacy facade 전용 테스트를 core/app 직접 검증 테스트로 바꿨다.
- obsolete 진입점 파일명을 제거하고 `epub_binder4.2.4.py`를 현재 진입점으로 확정했다.

변경 파일:

- `epub_binder4.2.4.py`
- `epub_binder_app/workers.py`
- `epub_binder_app/ui/dialogs.py`
- `epub_binder_app/ui/main_window.py`
- `epub_binder_app/ui/widgets.py`
- `epub_binder_bulid.bat`
- `AGENTS.md`
- `docs/REFACTORING_TASKS.md`
- `tests/test_app_package_smoke.py`
- `tests/test_advanced_merge_legacy.py`
- `tests/test_title_metadata.py`
- `tests/test_toc_helpers.py`
- `tests/test_txt_chapters.py`
- `tests/test_txt_conversion.py`
- `tests/test_txt_detection.py`
- `tests/test_worker_core_wrappers.py`

검증:

- `python -m compileall -q epub_binder4.2.4.py epub_binder_core tests epub_binder_app`: passed
- `python -m pytest -q`: 107 passed
- `epub_binder4.2.4.py` entry import smoke: passed

남은 위험:

- `main_window.py`와 `workers.py`는 아직 큰 클래스/메서드가 많아, 이후 리팩토링은 이 파일들을 더 작은 app 모듈로 나누는 방향이 안전하다.

### 2026-05-04

완료:

- Phase 9 metadata/title helper인 `_read_dc_tag`, 판권 HTML 작가/제목 추출, 제목 정규화, OPF 시리즈 제목 정리, 권 제목 탐색 계열을 `epub_binder_core.title_metadata`로 이동하고 legacy 함수명은 import re-export로 유지했다.
- 당시 진입점과 `epub_binder_bulid.bat`에 `epub_binder_core.title_metadata` 포함 경로를 추가했다.
- `tests/test_title_metadata.py`를 추가해 OPF CDATA, 판권 HTML 작가/제목 추출, 제목 정규화/정리, ZIP spine 앞쪽 권 제목 탐색, legacy facade re-export를 검증했다.
- `_toc_label_from_filename`, `_prefer_filename_toc_title`, `_toc_episode_no`와 filename label 신뢰도 판단 helper를 `epub_binder_core.toc`로 이동하고 legacy 함수명은 import re-export로 유지했다.
- `tests/test_toc_helpers.py`를 추가해 파일명 TOC 라벨 정리, filename/extracted title 우선순위, 일관된 화수 파일명 세트 판정, legacy facade re-export를 검증했다.
- `is_skip_page`, `extract_chapter_title`, `extract_all_subheadings`, `inject_subheading_anchors`, subnav heading 판정 helper를 `epub_binder_core.toc`로 이동하고 core skip detector를 legacy-parity 구현으로 맞췄다.
- TOC helper 테스트를 확장해 판권/표지/목차 skip 판정, 챕터 마커+부제 결합, subheading anchor 삽입, legacy facade re-export를 검증했다.
- `epub_binder_app.workers`가 metadata/title/TOC helper를 core에서 직접 import하도록 바꾸고 legacy의 `configure_worker_dependencies` 주입 호출을 제거했다.
- `epub_binder_app.ui.main_window`가 metadata/title/TOC helper를 core에서 직접 import하도록 바꾸고 legacy의 `configure_main_window_dependencies(**globals())`를 실제 필요한 rename/cover helper 명시 주입으로 축소했다.
- QSS와 체크박스 SVG 경로 생성을 `epub_binder_app.ui.style`로 이동하고 `main_window`/`dialogs`가 legacy 전역 주입 없이 app style 모듈을 직접 사용하도록 정리했다.
- `_guess_tail_volume_unit_from_zip`는 `epub_binder_core.title_metadata`로, `_xml_attr`는 `epub_binder_core.epub_io.xml_attr`로 이동하고 `main_window`가 직접 import하도록 정리했다.
- legacy wrapper 함수들을 core callable alias/partial로 줄이고 당시 legacy facade의 top-level 함수/클래스 정의를 제거했다.
- smoke 테스트에 legacy facade가 top-level function/class definition을 갖지 않는지 확인하는 검증을 추가했다.
- Phase 9 첫 작업으로 당시 legacy facade에 남은 top-level helper를 UI/표시, metadata/title, TOC/subheading, TXT wrapper, EPUB text wrapper, dependency adapter로 분류했다.
- `natural_sort_key`, `human_size`, `_safe_title`, `make_card`, `mk_btn`, `mk_lbl`를 `epub_binder_app.ui.helpers`로 이동하고 legacy 함수명은 import re-export로 유지했다.
- `epub_binder_app.ui.dialogs`와 `epub_binder_app.ui.main_window`가 공통 UI helper를 직접 import하도록 연결했다.
- TXT wrapper 함수들을 core 함수 alias로 줄여 legacy facade re-export에 가깝게 정리했다.
- EPUB text wrapper 중 `_html_to_plain_text`, `_cleanup_txt_text`, `_apply_txt_paragraph_indent`를 core 함수 alias로 줄이고, `extract_epub_text_sections`는 legacy skip-page detector 주입 wrapper로 유지했다.
- 당시 진입점, `epub_binder_bulid.bat`, smoke 테스트에 `epub_binder_app.ui.helpers` 포함을 추가했다.
- legacy facade smoke 테스트가 UI helper re-export까지 검증하도록 보강했다.
- Phase 8 이후에도 당시 legacy facade에 남은 helper/adapter 함수 축소 작업을 Phase 9로 추가했다.
- `EPUBMergerGUI`를 `epub_binder_app.ui.main_window`로 물리 이동했다.
- `main_window.py`에 `configure_main_window_dependencies` adapter를 두고 legacy helper 전역을 주입해 기존 GUI 동작 경로를 유지했다.
- 당시 legacy facade는 worker/widget/dialog/main window 클래스를 새 app 패키지에서 재노출하는 compatibility facade 형태로 축소했다.
- 당시 legacy facade의 동적 로더를 `load_compat_module` 중심으로 정리하고 기존 `load_legacy_module` 이름은 alias로 유지했다.
- 당시 진입점과 `epub_binder_bulid.bat`에 `epub_binder_app.ui.main_window` 포함 경로를 추가했다.
- smoke 테스트가 새 `main_window` import와 legacy `EPUBMergerGUI` re-export를 검증하도록 보강했다.
- `ScanWorker`, `StripOnlyWorker`, `MergeWorker`, `TxtEpubWorker`, `EpubTxtWorker`, `NaverSeriesFetchThread`를 `epub_binder_app.workers`로 물리 이동했다.
- worker 클래스가 legacy helper와 core wrapper를 계속 같은 방식으로 쓰도록 `configure_worker_dependencies` adapter를 추가하고 당시 legacy facade에서 재노출했다.
- `FileListWidget`을 `epub_binder_app.ui.widgets`로 물리 이동하고 legacy 파일에서 import하도록 연결했다.
- `TxtPreviewDialog`, `RenameBatchDialog`, `TocEditDialog`, `CoverPickerDialog`, `NaverSeriesCoverDialog`를 `epub_binder_app.ui.dialogs`로 물리 이동했다.
- 새 worker/widget/dialog 모듈 hidden-import를 `epub_binder_bulid.bat`에 추가했다.
- GUI를 띄우지 않는 import smoke 테스트를 worker/widget/dialog 모듈과 legacy re-export까지 확대했다.
- `epub_binder_app/`와 `epub_binder_app/ui/` 패키지 골격을 추가했다.
- 색상, 만료일, 기본 폰트, QSettings 조직/앱 이름을 `epub_binder_app.settings`로 분리했다.
- legacy 진입점과 새 실행 진입점이 settings 상수를 참조하도록 연결했다.
- `epub_binder_bulid.bat`에 `epub_binder_app`, `epub_binder_app.settings`, `epub_binder_app.ui` hidden-import를 추가했다.
- 새 app 패키지와 UI namespace import smoke 테스트, 빌드 스크립트 hidden-import 검증 테스트를 추가했다.
- Phase 0-7 체크박스가 모두 완료된 상태임을 확인하고, 후속 장기 작업으로 Phase 8 legacy GUI 파일 물리 분리 항목을 추가했다.
- `MergeWorker`의 최종 `container.xml`/`mimetype` 생성과 EPUB ZIP 패키징을 `epub_binder_core.epub_archive` helper 호출로 축소했다.
- `write_epub_shell_files`, `write_epub_directory_to_file` 회귀 테스트를 추가해 `mimetype` 첫 항목, stored 압축, timestamp, container rootfile을 검증했다.
- `NaverSeriesFetchThread` 안에 남아 있던 legacy HTML parser/download fallback을 제거하고 `fetch_naver_series_cover` core 호출만 남겼다.
- `NaverSeriesCoverDialog._parse_product_no`에서 도메인 regex fallback을 제거하고 core `parse_product_no` 호출만 남겼다.
- `format_worker_error`, `format_naver_fetch_error`를 core error 계층에 추가하고 legacy worker의 주요 실패 메시지 변환을 이 계층으로 위임했다.
- 실행 트래커를 `REFACTORING_TASKS.md`로 단일화하고 이 파일을 기준으로 갱신한다.
- 이름변경 미리보기 행 계산, 시리즈 표기 통일, 작가명 통일을 `epub_binder_core.rename_service`로 분리하고 GUI는 core preview row 표시 중심으로 축소했다.
- `TxtEpubWorker`의 TXT→EPUB 한 건 변환, 안전 파일명 생성, 중복 파일명 처리, 저장 로직을 `epub_binder_core.txt_conversion`으로 분리했다.
- `EpubTxtWorker`의 TXT/EPUB 입력별 텍스트 조립, 안전 파일명 생성, 중복 파일명 처리, 저장 로직을 `epub_binder_core.epub_text` 서비스로 분리했다.
- TXT 변환과 EPUB/TXT 출력 worker 호출 경로에 dataclass result type을 도입했다.
- OPF title과 HTML heading 우선순위를 함께 검증하는 이름변경 fixture를 추가했다.
- legacy wrapper parity 테스트를 `remove_invisible_chars`, `strip_epub_in_memory`, `add_noise_to_epub`, `compress_epub_images`, `extract_cover_image`, `extract_cover_candidates`까지 확대했다.
- zip 묶기 core grouping 결과가 legacy fallback grouping shape와 일치하는지 검증하는 parity 테스트를 추가했다.
- `parse_product_no` 직접 단위 테스트를 추가했다.
- `epub_binder_core.errors`에 `CoreError`, `InvalidEpubError`, `MissingMetadataError`, `CoverNotFoundError`, `NaverFetchError`를 추가하고 공통 base 상속 테스트를 추가했다.
- 현재 프로젝트 상태를 기준으로 실행 트래커를 새로 작성했다.
- 이미 분리된 core 모듈과 테스트를 체크 완료로 반영했다.
- 초안의 검증 결과를 현재 실제 결과인 `82 passed`로 보정했다.

변경 파일:

- `epub_binder4.2.4.py`
- `epub_binder_app/__init__.py`
- `epub_binder_app/settings.py`
- `epub_binder_app/workers.py`
- `epub_binder_app/ui/__init__.py`
- `epub_binder_app/ui/dialogs.py`
- `epub_binder_app/ui/helpers.py`
- `epub_binder_app/ui/main_window.py`
- `epub_binder_app/ui/style.py`
- `epub_binder_app/ui/widgets.py`
- `epub_binder_app/workers.py`
- `epub_binder_bulid.bat`
- `epub_binder_core/__init__.py`
- `epub_binder_core/title_metadata.py`
- `epub_binder_core/toc.py`
- `epub_binder_core/errors.py`
- `epub_binder_core/epub_archive.py`
- `epub_binder_core/epub_text.py`
- `epub_binder_core/rename_service.py`
- `epub_binder_core/txt_conversion.py`
- `REFACTORING_TASKS.md`
- `tests/test_core_errors.py`
- `tests/test_app_package_smoke.py`
- `tests/test_epub_archive_cleanup.py`
- `tests/test_epub_text_service.py`
- `tests/test_grouping.py`
- `tests/test_legacy_core_wrappers.py`
- `tests/test_naver_series.py`
- `tests/test_rename_service.py`
- `tests/test_title_parser.py`
- `tests/test_title_metadata.py`
- `tests/test_toc_helpers.py`
- `tests/test_txt_conversion_service.py`

검증:

- `python -m pytest -q tests\test_title_metadata.py tests\test_app_package_smoke.py`: 8 passed
- `python -m pytest -q tests\test_toc_helpers.py tests\test_merge.py tests\test_merge_plan.py tests\test_advanced_merge_legacy.py`: 41 passed
- `python -m pytest -q tests\test_toc_helpers.py tests\test_epub_archive_cleanup.py tests\test_epub_text.py tests\test_advanced_merge_legacy.py`: 15 passed
- `python -m pytest -q tests\test_app_package_smoke.py tests\test_toc_helpers.py tests\test_title_metadata.py`: 14 passed
- `python -m pytest -q tests\test_merge.py tests\test_merge_plan.py tests\test_advanced_merge_legacy.py tests\test_epub_text.py tests\test_txt_conversion.py`: 43 passed
- `python -m pytest -q tests\test_app_package_smoke.py tests\test_legacy_core_wrappers.py tests\test_toc_helpers.py tests\test_title_metadata.py`: 21 passed
- `python -m pytest -q`: 116 passed
- `python -m compileall -q epub_binder4.2.4.py epub_binder_core tests epub_binder_app`: passed
- `python -m py_compile epub_binder4.2.4.py`: passed

남은 위험:

- Phase 9 체크박스는 모두 완료됐다.
- 현재 트래커에 남은 미완료 체크박스는 없다.
