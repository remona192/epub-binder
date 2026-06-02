# AGENTS.md

이 프로젝트는 Windows PyQt6 기반 EPUB Binder 데스크톱 앱이다.

새 채팅에서 코딩 작업을 시작하면 반드시 이 파일을 먼저 읽고, 이어서 루트 `README.md`를 읽는다. `README.md`는 기능별 진입점과 작업 로드맵 역할을 한다.

## 기본 원칙

- 기존 코드 구조를 우선 따른다.
- 요청이 명확하면 바로 구현한다.
- 불필요한 대규모 리팩토링은 피한다.
- 변경 후에는 수정 내용과 테스트 결과를 짧게 보고한다.
- 사용자가 명시적으로 요청하기 전에는 커밋하지 않는다.
- 생성물, 캐시, 빌드 결과물은 소스 변경으로 취급하지 않는다.

## 커밋 규칙

- 커밋 메시지는 한국어로 쓴다.
- prefix는 `fix:`, `feat:`, `refactor:`, `test:`, `build:`, `docs:` 중 하나를 사용한다.

## 프로젝트 구조

- `README.md`: 빠른 작업 지도, 기능별 진입점, 빌드/검증 명령.
- `epub_binder4.3.4.py`: 오리지널 실행 진입점.
- `epub_binder5.1.0_public.py`: 공개용 실행 진입점.
- `epub_binder_bulid.bat`: 현재 빌드 스크립트. `SCRIPT`와 `EXE_NAME` 값을 기준으로 빌드 대상을 판단한다.
- `epub_binder_app/`: PyQt6 UI, 설정, worker thread, widgets, dialogs, main window.
- `epub_binder_core/`: EPUB/TXT/표지/네이버 시리즈/목차/중복 정리 순수 로직.
- `tests/`: pytest 기반 회귀 테스트와 fixture.
- `config/`: 아이콘 등 실행/빌드에 필요한 정적 자원.
- `docs/`: 사용자 설명서, 프로젝트 지도, 리팩토링 기록.

## 자주 쓰는 명령

문법 확인:

```powershell
python -m compileall -q epub_binder_app epub_binder_core epub_binder4.3.4.py epub_binder5.1.0_public.py
```

테스트:

```powershell
python -m pytest -q
```

EXE 빌드:

```powershell
cmd /c "echo. | epub_binder_bulid.bat"
```

`pytest`가 없으면 설치 필요를 보고하고, 가능한 경우 `compileall`이나 `py_compile`로 최소 검증한다.

## 작업 규칙

- 가능한 로직 변경은 `epub_binder_core/`에 두고 테스트를 붙인다.
- GUI/worker 변경은 `epub_binder_app/`에서 처리한다.
- UI 관련 작업은 `README.md`의 기능별 진입점을 보고 필요한 구간만 좁혀 읽는다.
- 실행 진입점은 얇게 유지하고, 빌드명 변경 때만 진입 파일과 빌드 스크립트 참조를 함께 갱신한다.
- 사용자에게 보이는 기능 결과를 바꾸지 않는 리팩토링을 우선한다.
- EPUB 수정은 ZIP 구조, OPF 경로, manifest, spine, 표지, 목차 참조를 깨지 않게 한다.
- 네이버 시리즈 테스트는 fixture와 mock을 사용하고 실시간 네트워크 의존을 만들지 않는다.

## 생성물 규칙

다음은 소스 변경으로 취급하지 않는다.

- `.venv/`
- `build/`
- `dist/`
- `*.spec`
- `*.exe`
- `__pycache__/`
- `.pytest_cache/`
- `recovered_from_exe/`
- `_check.svg`

## 하위 에이전트 기준

- 기능 추가, 버그 수정, GUI 연결, EPUB 병합/이름 변경/TXT/표지/네이버 시리즈 작업은 `.codex/agents/feature-developer.toml`을 참고한다.
- 테스트 추가, fixture 작성, 회귀 케이스 정리, 검증 계획은 `.codex/agents/test-engineer.toml`을 참고한다.
- 구조 개선, 중복 제거, 기능 변경 없는 리팩토링은 `.codex/agents/refactoring-engineer.toml`을 참고한다.
