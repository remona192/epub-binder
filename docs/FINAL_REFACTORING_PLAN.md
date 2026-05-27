# 기능 변경 없는 최종 리팩토링안

## 목표

이 계획의 목표는 기능을 새로 만들지 않고, 현재 동작을 보존한 상태에서 코드 책임을 분리해 버그 가능성을 줄이는 것이다.

핵심 원칙은 세 가지다.

- 사용자가 보는 결과는 바꾸지 않는다.
- 레거시 대형 파일은 테스트로 고정한 뒤 작은 단위로 분리했고, 최종적으로 제거한다.
- GUI는 입력과 표시만 담당하고, EPUB/TXT/네이버/압축 로직은 `epub_binder_core/`가 담당하게 만든다.

## 현재 구조 요약

현재 프로젝트는 아래 구조다.

```text
epub_binder4.2.4.py
  -> 현재 실행 진입점, PyInstaller 포함용 app/core import, GUI 직접 실행

epub_binder_app/
  -> PyQt6 GUI, QThread worker, settings, widgets, dialogs, main window

epub_binder_core/
  -> EPUB/TXT/네이버/압축/표지/목차 순수 로직 패키지
```

현재 분리된 core 책임은 다음과 같다.

| 모듈 | 현재 책임 |
|---|---|
| `title_parser.py` | 파일명/제목/작가/권수/화수 파싱, 이름 포맷 |
| `epub_io.py` | EPUB container, OPF, manifest, spine, NCX, heading 읽기 |
| `naver_series.py` | 네이버 시리즈 HTML 파싱, 표지 선택, 다운로드 클라이언트, mock 가능한 fetch service |
| `cover.py` | EPUB 표지 추출과 표지 후보 수집 |
| `epub_cleanup.py` | 보이지 않는 문자 스캔/제거, 판권/목차 페이지 제거 |
| `epub_archive.py` | ZIP 경로 정규화, 압축 방식, timestamp, 이미지 노이즈/압축 |
| `merge.py` | 단순 EPUB 병합 서비스 |
| `merge_plan.py` | 고급 legacy 병합의 표지/목차 skip 판단, 이미지 pruning 계획, OPF 렌더링, NCX navPoint 렌더링 |
| `toc.py` | skip page 판별, HTML 텍스트 정리 |
| `grouping.py` | 이름변경 탭의 같은 시리즈 압축 묶기 그룹 계산 |
| `epub_text.py` | EPUB HTML 본문 추출과 TXT 출력용 정리/들여쓰기 |
| `txt_parser.py` | TXT 인코딩 감지와 기본 메타데이터 처리 |
| `txt_detection.py` | TXT 챕터 헤더 감지와 본문 분리 |
| `txt_chapters.py` | TXT 챕터 번호/양식 후처리 |
| `txt_epub.py` | TXT 챕터 목록의 EPUB 생성 |

테스트는 `tests/`에 있으며 현재 `title_parser`, `epub_io`, `naver_series`, `cover`, `epub_archive_cleanup`, `merge`, `merge_plan`, 고급 legacy merge 구조를 일부 검증한다.

## 현재 가장 큰 문제

1. 이전에는 단일 진입점 파일이 너무 많은 책임을 가졌지만, Phase 10에서 `epub_binder4.2.4.py`를 얇은 실행 진입점으로 정리했다.
   현재 남은 구조 리스크는 `main_window.py`와 `workers.py` 내부의 큰 클래스/메서드를 더 작게 나누는 것이다.

2. 레거시 facade와 core 함수 공존은 제거됐다.
   앞으로는 app 계층이 core 함수를 직접 호출하고, 새 도메인 규칙은 core에 추가한다.

3. 테스트가 아직 “사용자 버그 재현” 중심으로 충분하지 않다.
   core 단위 테스트는 생겼지만, 이름변경/권목차/TXT 변환/표지 제거/압축 묶기 같은 실제 버그 흐름을 모두 잠그지는 못한다.

4. EPUB 조작이 문자열/정규식 기반인 곳이 많다.
   유지보수는 가능하지만, OPF/manifest/spine/NCX 참조를 잘못 지우면 EPUB이 열리지만 내부 구조가 깨지는 버그가 생길 수 있다.

## 최종 목표 구조

목표는 아래 방향이다.

```text
PyQt6 화면/버튼
  -> QThread worker
    -> epub_binder_core service
      -> Result dataclass / typed error
```

각 계층의 책임은 다음처럼 제한한다.

| 계층 | 책임 | 금지 |
|---|---|---|
| GUI | 입력 받기, 옵션 표시, 결과/오류 표시 | EPUB ZIP 직접 수정 |
| Worker | 긴 작업 실행, progress emit, 취소/예외 전달 | 도메인 규칙 직접 구현 |
| Core service | 순수 로직, 파일/bytes 처리, 결과 반환 | PyQt import |
| Tests | fixture 기반 회귀 검증 | 실시간 네트워크 의존 |

## 리팩토링 순서

### 0단계: 현재 동작 고정

작업 전 기준을 만든다.

- `python -m compileall -q epub_binder4.2.4.py epub_binder_core epub_binder_app tests`
- `python -m pytest`
- pytest가 없으면 설치 필요를 기록하고 compileall만 먼저 통과시킨다.
- 기존 버그 사례를 fixture로 보존한다.
  - `쾌도무적 1권 - 1/2/3` 이름변경과 zip 묶기
  - `section0001.xhtml`의 `<h2 class="0">케이 18권</h2>` 제목 추출
  - 네이버 시리즈 `productNo=4433040` 작가 추출
  - 권목차/권표지 체크 여부에 따른 내부 표지 처리
  - TXT 챕터 번호/외전 양식 정규화

이 단계에서는 코드 구조를 바꾸지 않는다. 테스트와 fixture만 추가한다.

### 1단계: core wrapper 정리

과거 단일 파일 안의 “레거시 구현 후 core wrapper로 덮어쓰기” 구조를 명확하게 정리한다.

작업 방식:

- 기존 함수명은 유지한다.
- 함수 내부 구현은 core 호출만 남긴다.
- 과거 구현은 바로 삭제하지 않고, 테스트가 있는 함수부터 제거한다.
- 제거 전후 반환값이 같은지 fixture로 확인한다.

우선 대상:

- `remove_invisible_chars`
- `scan_invisible_chars`
- `strip_epub_in_memory`
- `add_noise_to_epub`
- `compress_epub_images`
- `apply_epub_timestamp`
- `extract_cover_image`
- `extract_cover_candidates`

완료 기준:

- GUI와 worker는 기존 함수명을 그대로 호출한다.
- 실제 로직은 `epub_binder_core/`에만 존재한다.
- 관련 테스트가 모두 통과한다.

### 2단계: 이름변경/압축 묶기 책임 분리

이름변경과 zip 묶기는 사용자 버그가 자주 생기는 영역이므로 먼저 고정한다.

대상 책임:

- 파일명 파싱
- OPF title/creator/headings 우선순위
- 권수/화수/파트 포맷
- 시리즈 zip key 생성
- 단일 파일은 압축 제외
- `1-1`, `1-2`, `1-1.` 같은 연속 시리즈 묶기

목표 모듈:

- 기존 `title_parser.py` 유지
- 필요하면 `rename.py` 또는 `grouping.py` 추가

완료 기준:

- `RenameBatchDialog`와 zip 묶기 UI는 core 결과만 받아 표시한다.
- 같은 입력 fixture에 대해 이름/zip key가 항상 동일하다.
- 파일명, OPF, HTML heading 우선순위가 테스트로 고정된다.

### 3단계: 목차/병합 책임 분리

병합은 EPUB 구조를 깨뜨리기 쉬우므로 가장 보수적으로 진행한다.

대상 책임:

- 권목차 생성
- 권표지 포함/제외
- 단일 목차 모드에서 내부 표지 파일 제거
- NCX label 생성
- spine/manifest 정합성 유지
- skip page 판별

목표 모듈:

- `merge.py`: 병합 orchestration
- `toc.py`: 목차 라벨, skip page, heading 추출
- `cover.py`: 표지 후보와 기본 표지 선택

주의:

- 현재 `merge.py`는 “단순하고 보수적인 병합 서비스”다.
- 레거시 고급 병합 경로를 바로 대체하지 않는다.
- 먼저 레거시 병합 결과의 주요 구조를 fixture로 고정한 뒤 core로 책임을 옮긴다.

완료 기준:

- 권목차 체크/해제에 따른 OPF, NCX, spine, 내부 표지 파일 상태가 테스트된다.
- EPUB을 열 수 있는지만 보지 않고, ZIP 내부 참조까지 검증한다.

### 4단계: TXT 변환 책임 분리

TXT 변환은 입력 양식이 다양하므로 파서와 출력기를 나눈다.

대상 책임:

- TXT 인코딩 감지
- 챕터 탐지
- 외전/화수/권수 정규화
- 짧은 챕터 병합
- EPUB 생성

목표 모듈:

- `txt_parser.py`: 텍스트 디코딩, 챕터 탐지, 챕터 번호 정규화
- `txt_epub.py`: 챕터 목록을 EPUB으로 생성

완료 기준:

- `detect_chapters`, `filter_ascending_chapters`, `fill_numeric_gaps`, `merge_short_chapters`, `normalize_chapter_style`, `build_txt_epub`가 core로 이동한다.
- 레거시 `TxtEpubWorker`는 progress emit과 core 호출만 담당한다.
- 다양한 챕터 표기 fixture가 같은 출력 양식으로 정규화된다.

### 5단계: EPUB 텍스트 추출 책임 분리

대상 책임:

- EPUB HTML 읽기
- HTML을 plain text로 변환
- 불필요한 공백/문단 정리
- TXT 출력 섹션 구성

목표 모듈:

- `epub_text.py`

완료 기준:

- `extract_epub_text_sections`, `_html_to_plain_text`, `_cleanup_txt_text`, `_apply_txt_paragraph_indent`가 core로 이동한다.
- `EpubTxtWorker`는 파일 선택, progress, 결과 저장만 담당한다.

### 6단계: 네이버 시리즈 책임 분리

현재 `naver_series.py`에는 parser/client가 있지만, 레거시 `NaverSeriesFetchThread` 안에도 상세 URL 후보 수집과 다운로드 흐름이 남아 있다.

대상 책임:

- productNo 파싱
- 상세 HTML 파싱
- 작가/제목 추출
- 표지 URL 후보 수집
- 이미지 다운로드
- SSL fallback

목표 구조:

```text
NaverSeriesCoverDialog
  -> NaverSeriesFetchThread
    -> NaverSeriesClient / parser functions
```

완료 기준:

- HTML 파싱은 `naver_series.py`에만 둔다.
- UI thread는 쿠키, productNo, progress message만 관리한다.
- 네트워크 없는 parser 테스트와 mock 기반 client 테스트를 분리한다.

### 7단계: 예외/결과 타입 통일

core 함수가 제각각 tuple, dict, bool, 예외를 섞어 반환하면 GUI에서 버그가 생기기 쉽다.

정리 방향:

- 새 core API는 dataclass Result를 반환한다.
- GUI 표시용 문구는 core가 아니라 adapter/worker에서 만든다.
- core 예외는 의미 있는 타입으로 나눈다.

예시:

```text
CoreError
  - InvalidEpubError
  - MissingMetadataError
  - CoverNotFoundError
  - NaverFetchError
```

완료 기준:

- worker는 core 예외를 잡아 사용자 메시지로 변환한다.
- core는 PyQt `QMessageBox`, signal, widget을 알지 못한다.

## 테스트 전략

리팩토링은 테스트 없이 진행하지 않는다.

| 테스트 종류 | 목적 |
|---|---|
| 단위 테스트 | parser, path, cover, cleanup, archive, toc 같은 순수 함수 검증 |
| fixture 테스트 | 실제 EPUB/HTML/TXT 구조를 작게 재현 |
| parity 테스트 | 레거시 함수명 호출 결과와 core 결과가 같은지 확인 |
| 구조 테스트 | OPF manifest/spine/NCX 참조가 깨지지 않았는지 확인 |
| 수동 smoke | GUI에서 대표 흐름이 꺼지지 않는지 확인 |

우선 추가할 회귀 테스트:

- 이름변경: OPF title보다 HTML heading이 더 신뢰되는 케이스
- 이름변경: `[작가] 시리즈 1 1권.epub` 중복 권수 제거
- 압축 묶기: 같은 시리즈의 `1-1`, `1-2`, `1-1.`이 분리되지 않는지
- 병합: 권목차/권표지 on/off에 따른 NCX와 내부 표지 파일 상태
- TXT 변환: `1.`, `1화`, `외전123` 혼합 입력 정규화
- 네이버: 추천 영역 작가가 아니라 상세 영역 작가를 선택하는지

## 위험 요소와 대응

| 위험 | 대응 |
|---|---|
| 한글 인코딩/터미널 mojibake | 파일은 UTF-8로 유지하고, 콘솔 표시보다 Python 테스트 결과를 신뢰한다. |
| EPUB ZIP 구조 손상 | `mimetype` 첫 엔트리/무압축, OPF 경로, manifest/spine 참조를 테스트한다. |
| 정규식 기반 OPF 수정 오류 | 가능한 곳부터 `ElementTree` 기반으로 옮기되, 출력 차이는 fixture로 비교한다. |
| GUI thread 종료/크래시 | worker는 core 호출과 signal emit만 담당하게 줄인다. |
| 네이버 실시간 페이지 변경 | parser는 fixture 테스트, client는 mock 테스트로 분리한다. |
| 한 번에 큰 변경 | 단계별로 wrapper 유지, 테스트 통과 후 삭제한다. |

## 작업 순서 권장안

1. 테스트 보강부터 진행한다.
2. 이미 wrapper가 있는 cleanup/archive/cover부터 core 단일 구현으로 정리한다.
3. 이름변경/압축 묶기 로직을 `title_parser.py` 또는 새 grouping 모듈로 모은다.
4. 병합/목차/표지 제거는 fixture를 충분히 만든 뒤 옮긴다.
5. TXT 변환과 EPUB 텍스트 추출을 각각 별도 core 모듈로 분리한다.
6. 네이버 fetch thread 내부 parser를 `naver_series.py`로 이동한다.
7. 마지막에 worker/result/error 타입을 통일한다.

## 범위에서 제외

이번 리팩토링에서 하지 않을 일:

- UI 디자인 변경
- 새 기능 추가
- 네이버 시리즈 지원 범위 확대
- EPUB3 완전 지원 같은 스펙 확장
- 빌드 시스템 전면 교체
- 파일명/출력 양식의 의도적 변경

## 완료 기준

최종 완료 상태는 다음과 같다.

- `epub_binder4.2.4.py`는 얇은 실행 진입점으로 남는다.
- `epub_binder_app/`은 GUI, dialog, worker, settings를 담당한다.
- `epub_binder_core/`는 EPUB/TXT/네이버/압축/표지/목차 순수 로직을 담당한다.
- core 모듈은 PyQt6를 import하지 않는다.
- 기존 사용자 흐름은 유지되어 기능 변경이 없다.
- 대표 버그 케이스가 pytest fixture로 고정된다.
- `python -m compileall -q epub_binder4.2.4.py epub_binder_core epub_binder_app tests`가 통과한다.
- `python -m pytest`가 통과한다.

## 병렬 작업 가능성

초기 테스트 보강 이후에는 아래처럼 나눌 수 있다.

| 작업 | 담당 영역 | 의존성 |
|---|---|---|
| cleanup/archive/cover 정리 | `epub_binder_core/cover.py`, `epub_archive.py`, `epub_cleanup.py` | 테스트 보강 |
| 이름변경/압축 묶기 | `title_parser.py`, 새 grouping 모듈 | 테스트 보강 |
| 네이버 parser/client 정리 | `naver_series.py` | fixture 보강 |
| TXT 변환 분리 | 새 `txt_parser.py`, `txt_epub.py` | TXT fixture 보강 |
| 병합/목차 분리 | `merge.py`, `toc.py`, `cover.py` | 병합 fixture 보강 |

추천 순서는 병렬보다 안정성을 우선한다. 특히 `main_window.py`와 `workers.py`는 충돌이 많이 나는 파일이므로 동시에 여러 작업자가 수정하지 않는 편이 안전하다.

## 최종 판단

이 프로젝트의 최종 리팩토링 방향은 “레거시 파일을 얇게 줄인 뒤 제거하고, app/core 경계를 유지하기”다.

가장 중요한 성공 조건은 코드 줄 수 감소가 아니다. 기존 사용자가 보던 결과를 깨뜨리지 않으면서, 버그가 났을 때 `epub_binder_core/`의 작은 함수와 fixture 테스트에서 원인을 찾을 수 있게 만드는 것이다.
