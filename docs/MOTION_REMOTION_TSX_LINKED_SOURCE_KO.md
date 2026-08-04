# Motion Designer TSX Linked Source

## 목적

Motion Designer는 `.tsx` 또는 `.jsx` 파일을 다른 형식으로 바꾸거나 원본을
덮어쓰지 않는다. 사용자가 신뢰한 소스 파일을 프로젝트 레이어로 링크하고,
Tiger Studio의 격리된 React/esbuild 호환 런타임이 해당 원본을 직접 번들링해
프레임 캐시를 만든다.

## 사용자 흐름

1. `Objects > Remotion TSX`를 선택한다.
2. 원본 `.tsx` 또는 `.jsx` 파일을 고른다.
3. 실행 전 정적 검사가 import, default export, 동적 코드 사용 여부를 보여준다.
4. 신뢰 확인 후 필요한 로컬 런타임이 없으면 설치 안내가 나온다.
5. 원본 경로와 SHA-256을 가진 `remotion_tsx` 레이어가 생성된다.
6. 원본이 바뀌면 기존 프레임 캐시는 즉시 stale 상태가 되며 `Refresh`로 다시
   읽는다.

기본 링크 길이는 5초다. 액션의 `duration_ms`로 바꿀 수 있으며, 같은 원본 해시,
해상도, FPS, 길이의 완전한 캐시는 다시 렌더하지 않고 재사용한다.

## 보존 및 안전 계약

- 원본 소스는 수정, 복사 대체, 자동 포맷 또는 Tiger 전용 문법 변환을 하지 않는다.
- 정적 검사는 소스를 실행하지 않는다.
- TSX 실행은 명시적인 `trust_source=true` 이후에만 허용한다.
- 캐시는 `external/tools/remotion_tsx_runtime/jobs`에 생성되는 재생성 가능 데이터다.
- 프로젝트에는 원본 URI, 해시, 런타임 계약과 캐시 메타데이터가 저장된다.
- 원본 해시가 달라지거나 파일이 없으면 오래된 화면을 보여주지 않고 투명 프레임과
  명시적 validation 경고/오류를 사용한다.

## 현재 호환 범위

Tiger 호환 런타임은 React 컴포넌트와 다음 Remotion 스타일 API를 제공한다.

- `useCurrentFrame`
- `useVideoConfig`
- `interpolate`
- `spring`
- `random`
- 기본 `next/image` 호환 컴포넌트

상대 경로 import는 esbuild가 원본 파일 위치를 기준으로 해석한다. 그 외 외부 npm
패키지는 정적 검사에서 unsupported import로 보고하며 자동으로 내려받거나 실행하지
않는다. 이는 Remotion 패키지 전체 또는 임의 웹 프로젝트 전체 호환을 뜻하지 않는다.

## 자동화 액션

- `motion.remotion_tsx.runtime.status`
- `motion.remotion_tsx.runtime.install`
- `motion.remotion_tsx.inspect`
- `motion.remotion_tsx.import`
- `motion.remotion_tsx.refresh`

`import`에서 `prepare_preview=false`를 사용하면 소스를 실행하지 않고 링크만 만들 수
있다. 프리뷰 준비에는 `trust_source=true`가 필요하다.

## 검증 기준

- `tools/qa_remotion_tsx_corpus.py`로 소스 집합의 정적 호환성을 검사한다.
- `tools/render_remotion_tsx_cache.py`로 실제 Qt WebEngine 프레임을 렌더한다.
- `tools/launch_remotion_tsx_sample.py`로 실제 Motion Designer에서 반복 재생한다.
- 원본 변경 전후 SHA-256과 캐시 무효화를 테스트한다.
- 프레임 캡처 배경은 알파를 유지해 영상 위 합성을 막지 않아야 한다.
