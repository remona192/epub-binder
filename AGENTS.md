# AGENTS.md

이 프로젝트는 Windows용 EPUB Binder 데스크톱 앱이다. 현재 실행 진입점과 exe 이름은
`epub_binder_bulid.bat`의 `SCRIPT`와 `EXE_NAME` 값을 기준으로 판단한다.

## 프로젝트 구조

- 현재 실행 진입점: 루트의 `epub_binder*.py` 중 빌드 스크립트 `SCRIPT`가 가리키는 파일.
- 현재 배포 exe: `dist/` 안의 `EXE_NAME` 기반 exe.
- `epub_binder_app/`: PyQt6 앱 계층. settings, worker thread, widgets, dialogs, main window가 있다.
- `epub_binder_core/`: EPUB/TXT/네이버 시리즈/표지/목차/압축 관련 순수 로직.
- `tests/`: pytest 기반 core/app 회귀 테스트와 fixture.
- `tests/fixtures/`: 오프라인 테스트용 HTML/TXT/EPUB fixture.
- `config/`: 아이콘 등 실행/빌드에 필요한 정적 설정 자산.
- `epub_binder_bulid.bat`: Windows PyInstaller 빌드 스크립트이자 현재 빌드명 기준 파일.

## 자주 쓰는 명령

- 앱 실행: `epub_binder_bulid.bat`의 `SCRIPT` 값을 확인한 뒤 `python <SCRIPT>`
- 문법 검사: `python -m compileall -q <SCRIPT> epub_binder_core epub_binder_app tests`
- 테스트: `python -m pytest -q`
- exe 빌드: `.\epub_binder_bulid.bat`

`pytest`가 없으면 설치 필요를 보고하고, 가능한 경우 `compileall`이나 `py_compile`로 최소 검증한다.

## 작업 규칙

- 가능한 로직 변경은 `epub_binder_core/`에 두고 테스트를 붙인다.
- GUI/worker 변경은 `epub_binder_app/`에 둔다.
- 실행 진입점은 얇게 유지하고 빌드명 변경 때만 파일명/스크립트 참조를 함께 갱신한다.
- 사용자에게 보이는 기능 결과를 바꾸지 않는 리팩토링을 우선한다.
- EPUB 수정은 ZIP 구조, OPF 경로, manifest, spine, 표지, 목차 참조를 깨지 않게 한다.
- 네이버 시리즈 테스트는 fixture와 mock을 사용하고 실시간 네트워크 의존을 만들지 않는다.
- `.venv/`, `build/`, `*.spec`, exe 루트 복사본, `__pycache__/`, `.pytest_cache/`는 생성물로 취급한다.

## 자동 에이전트 선택

- 기능 추가, 버그 수정, GUI 연결, EPUB 병합/이름변경/TXT/표지/네이버 시리즈 작업은
  `.codex/agents/feature-developer.toml`을 사용한다.
- 테스트 추가, fixture 작성, 회귀 케이스 정리, 검증 계획은
  `.codex/agents/test-engineer.toml`을 사용한다.
- 구조 개선, 중복 제거, 레거시 함수 분리, 기능 변경 없는 리팩토링은
  `.codex/agents/refactoring-engineer.toml`을 사용한다.

## 서브 에이전트 사용 기준

- 큰 작업, Phase 단위 작업, 기능 개발/테스트/리팩토링이 섞인 작업은 서브 에이전트를 반드시 활용한다.
- 최소 하나 이상의 서브 에이전트에 기능, 테스트, 리팩토링 중 독립 가능한 책임을 위임한다.
- 같은 파일을 여러 에이전트가 동시에 수정하지 않도록 책임 범위를 나눈다.
- 최종 통합자는 테스트 실행과 `REFACTORING_TASKS.md` 갱신을 책임진다.
