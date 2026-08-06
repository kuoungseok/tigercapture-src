# Painter UI Figma 컴포넌트 속성 바인딩 호환성

## 보존 원칙

Figma의 `componentPropertyReferences`는 필드 하나를 하나의 바인딩 슬롯으로
센다. 가져오기 과정에서 지원 필드는 Painter의 활성
`component_property_bindings`로 변환하고, 아직 지원하지 않는 필드나 컴포넌트
문맥이 사라진 바인딩은 원본 값을 포함한 복구 레코드로 남긴다.

```text
원본 componentPropertyReferences 슬롯
  = 활성 component_property_bindings
  + figma_component_property_bindings 복구 슬롯
```

원본 매핑은 `content.figma_component_property_references`에 그대로 보관한다.
따라서 JSON 저장·다시 열기와 UMG 전달 이후에도 Figma 필드명과 속성 ID를
검사할 수 있다.

## Native와 복구 경로

현재 Painter가 의미를 아는 Figma 필드는 다음 Painter 경로로 활성화된다.

- `characters` → `content.text`
- `visible` → `visible`
- `mainComponent`/인스턴스 확장 중 유효한 기존 경로 → 해당 Painter 속성 경로

지원하지 않는 미래 필드는 삭제하지 않고
`figma_component_property_reference_field_unsupported`로 복구한다. 지원 필드의
속성 ID가 비어 있으면 `figma_component_property_reference_value_missing`으로
복구한다. 인스턴스 확장 때문에 원래 컴포넌트 문맥과 다시 연결해야 하는
바인딩은 `figma_component_property_binding_requires_component_relink`로
표시한다.

Figma 호환성 검사에는 활성 바인딩마다 `native` 행, 복구 슬롯마다 `blocked`
행이 생긴다. 이 방식으로 지원 여부와 원본 보존 여부를 각각 확인할 수 있다.

## UMG 경계

TigerStudioUMG 문서의 `PainterSource.PayloadJson`에는 다음 세 항목을 함께
전달한다.

- `component_property_bindings`: Painter 활성 바인딩
- `figma_component_property_bindings`: 복구 슬롯
- `figma_component_property_references`: Figma 원본 매핑

현재 UMG 런타임은 Figma 컴포넌트 속성 ID를 Widget Blueprint 파라미터에
자동 연결하지 않는다. 그러므로 활성 바인딩은
`figma_component_property_binding_requires_umg_component_parameter_binding`
blocker로 명시한다. 복구 슬롯은 각각 컴포넌트 재연결 또는 미지원 필드
blocker를 낸다. 조용히 정적인 값으로 고정해 성공으로 보고하지 않는다.

## 실제 코퍼스 증거

2026-08-05 fast 20 공개 코퍼스 결과:

```text
원본 112 = 활성 95 + 복구 17
20 / 20 cases PASS
```

복구 슬롯이 있는 4개 케이스는 매니페스트에
`component_property_binding_recovery` 보존 조건을 고정했다. 전체 코퍼스
러너도 케이스별·집계별로 위 보존식을 검사하며 하나라도 맞지 않으면 실패한다.

증거 리포트:

```text
debugCapture/painter_ui_figma_m3_reactions_fast20/report.json
debugCapture/painter_ui_figma_m3_reactions_nightly4/report.json
```

