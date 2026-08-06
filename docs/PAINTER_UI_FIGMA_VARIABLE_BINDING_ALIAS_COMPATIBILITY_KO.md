# Painter UI Figma 변수 바인딩 alias 호환성

## 슬롯 단위 보존식

Figma `boundVariables` 호환성은 바인딩이 있는 노드 수만으로 판단하지 않는다.
각 필드의 scalar 값은 1개 alias 슬롯이고, 배열 값은 각 원소가 1개 슬롯이다.
배열의 `null`, 빈 객체, 비정상 값도 원본에 존재한 슬롯이므로 반드시 센다.
빈 배열만 슬롯이 0개다.

```text
source figma_variable_binding_alias
  = imported object alias + imported artboard alias
  = import_report.variable_binding_count
  = native + recovered + unresolved + blocked
```

기존 `variable_bindings` feature는 바인딩을 가진 노드 수로 유지한다. 기존
매니페스트와 보고서 소비자의 호환성을 깨지 않으면서, 새
`figma_variable_binding_alias` feature가 실제 무손실 여부를 검사한다.

## 가져온 레코드 상태

- `native`: Figma 변수 정의와 Painter token 경로가 모두 연결됨
- `recovered`: 원본 alias는 유효하지만 한 Painter 경로에 여러 alias가 있어
  개별 paint 재연결이 필요함
- `unresolved`: alias ID는 있으나 현재 문서에 변수 정의가 없음
- `blocked`: alias ID가 없거나 필드를 아직 지원하지 않거나, 아트보드에 직접
  연결되어 명시적 재연결이 필요함

알 수 없는 상태는 `unclassified`로 따로 세며, 값이 0이 아니면 보존 게이트가
실패한다. 케이스별 오류 코드는
`figma_variable_binding_alias_count_not_conserved`이다.

top-level `COMPONENT`는 Painter에서 아트보드 원본이면서 편집 가능한 컴포넌트
객체이기도 하다. 같은 Figma alias를 객체와 아트보드 복구 양쪽에 복사하지
않고 객체 레코드 하나만 유지한다. 일반 top-level frame은 Painter 객체가
아니므로 alias를 아트보드 복구 레코드로 보존한다.

## 고정 공개 코퍼스 증거

2026-08-05 fast 20:

```text
source 145 = imported 145 = import report 145
imported 145 = object 144 + artboard 1
status 145 = native 0 + recovered 0 + unresolved 101 + blocked 44
unclassified 0
20 / 20 PASS
```

2026-08-05 nightly 4 전체:

```text
source 3,252 = imported 3,252 = import report 3,252
imported 3,252 = object 3,233 + artboard 19
status 3,252 = native 0 + recovered 0 + unresolved 3,249 + blocked 3
unclassified 0
4 / 4 PASS
```

핵심 `grida.auto-layout.archive` 단일 케이스:

```text
source 3,231 = imported 3,231 = import report 3,231
imported 3,231 = object 3,212 + artboard 19
status 3,231 = unresolved 3,228 + blocked 3
```

매니페스트에는 실제 alias가 있는 fast 3개와 nightly 2개 케이스에
`figma_variable_binding_alias` source/preserve 조건을 고정했다.

증거 리포트:

```text
debugCapture/painter_ui_figma_m6_variable_alias_fast20/report.json
debugCapture/painter_ui_figma_m6_variable_alias_nightly4/report.json
```

