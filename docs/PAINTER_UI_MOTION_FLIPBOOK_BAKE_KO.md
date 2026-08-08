# Motion Designer → UMG Flipbook Atlas Bake

`app/painter_ui_flipbook_bake.py`는 Motion Designer의
`MotionComposition`을 별도 모사 렌더러가 아닌 실제
`MotionExportRenderer`로 샘플링해 투명 RGBA PNG atlas와 UMG schema 12
flipbook record를 만든다.

현재 계약은 다음과 같다.

- 샘플 시간은 누적 덧셈 없이 `frame_index * 1000 / fps`의 유리수로 계산한다.
- 프레임은 row-major로 배치하며 fps, frame 수, cell 크기, grid와 atlas 한계는
  UMG 계약 및 기본 최대 8192px 안에서 검증한다.
- manifest에는 composition ID/revision/input hash, 각 프레임의 RGBA/PNG hash,
  atlas PNG hash와 정확한 샘플 시간 분수를 기록한다.
- 출력 이름은 입력·설정·atlas hash 기반이다. 동일 byte 출력만 재사용하며 기존
  파일이 다르면 `motion_flipbook_output_collision`으로 중단하고 덮어쓰지 않는다.
- 셰이더 소스 입력은 받지 않는다. UMG의 고정
  `tiger_ui_flipbook_atlas_custom_hlsl_v1` generator만 기록한다.

Unreal의 현재 Material Time은 `global_time`이다. 따라서 자동 재생/ambient loop는
Material-ready지만 click/hover 같은 event-triggered 재생은 atlas를 생성하더라도
`flipbook_trigger_requires_dynamic_material_time_origin` blocker를 남긴다. 이벤트
발생 시점으로 시간을 reset할 Dynamic Material parameter 경로가 구현되기 전에는
이 상태를 지원 완료로 해석하면 안 된다.

## Painter 문서 부착

`app/painter_ui_flipbook_document.py`의
`attach_flipbook_bake_to_painter_document()`는 bake 결과를 UI 없이 검증하고 새
Painter 문서 사본을 반환한다.

- 대상은 `image`와 `rectangle`만 허용한다.
- atlas/manifest의 존재, byte, SHA-256, schema와 UMG record를 다시 검증한다.
- `content.flipbook`에는 M4 adapter가 읽는 lower-case authored 필드만 기록한다.
- manifest 경로/hash, atlas 경로/hash, composition revision/hash, playback scope,
  time origin과 blocker는 `content.flipbook_bake`에 복구 메타데이터로 남긴다.
- 대상의 나머지 content, style, constraints, 계층, interaction, accessibility는
  변경하지 않으며 입력 문서도 제자리에서 수정하지 않는다.
- 같은 bake의 반복 부착은 no-op이고 revision을 다시 증가시키지 않는다.

## 제품 UI 워크플로

Motion Delivery 패널의 `Bake Flipbook`은
`app/painter_ui_flipbook_workflow.py`의 UI 없는 공통 워크플로를 호출한다.

- 선택 대상은 stable Motion binding이 연결된 `image` 또는 `rectangle`이어야
  하며, composition과 binding ID를 다시 검증한다.
- `autoplay && loop`이고 binding trigger와 문서의 `play_animation`
  interaction이 모두 없을 때만 `ambient_loop`로 분류한다. 그 밖의 click,
  hover, transition/state 재생은 `event_triggered` blocker를 유지한다.
- atlas와 manifest는 `AppDataLocation/painter_ui_flipbooks` 아래에 저장한다.
  document/object ID는 읽을 수 있는 slug와 SHA-256 suffix로 변환하므로 Figma
  `1:2`, slash, `..`가 Windows 경로나 상위 디렉터리를 침범할 수 없다.
- 빈 경로, 상대 AppData 경로, `debugCapture` 아래 경로는 안정적인 blocker로
  거부한다.
- 성공한 변경은 기존 문서를 undo에 넣은 다음 교체하고 dirty/overlay 상태를
  갱신한다. 실패는 원본 문서와 파일을 조용히 바꾸지 않는다.

## Painter → Tiger UMG 변환

Painter UMG adapter v10은 부착된 `content.flipbook`을 schema 13 문서의
하위 호환 typed schema-12
`Layer.Flipbook`으로 변환하고 atlas를 별도 `FlipbookAtlas` texture resource로
패키징한다. 이때 일반 `AssetId`, `ImageFill`, `Material`은 비워 시각 소스가
중복되지 않게 한다. `content.flipbook_bake.material_ready`와
`block_reasons`도 읽고 `PayloadJson`에 provenance를 보존하므로,
`event_triggered` 결과가 일반 Material로 잘못 분류되지 않는다.

UE 5.8 실증은 다음을 모두 통과했다.

- Editor Development, Game Development, Game Shipping 플러그인 빌드
- Widget Blueprint compile/save/reopen 및 4개 Material brush 직렬화 참조
- atlas Texture2D에서 4개 Material package로 이어지는 참조
- Material마다 정확히 12개 expression: Texture Coordinate 1, Time 1,
  Scalar Parameter 8, 고정 Custom HLSL 1, Texture Sample Parameter 1
- 실제 `FWidgetRenderer` 256×256 캡처의 2×2 red/green/blue/yellow 셀 비교
- D3D12 gamma-corrected 기대값 대비 정확한 256×256 크기와 셀 위치·상호
  구분을 확인하고, 각 셀의 4px inset 내부 모든 픽셀에서 RGB 채널 오차 2
  이하, alpha 255, Material compile failure 0건
- 셀별 RGB MAE 0.667, 1.333, 0.667, 0.667은 진단용이다. 평균값으로
  한 픽셀 오류를 숨기지 않으며 RGB 3-code 오류, alpha 254, 셀 교환·중복은
  각각 회귀 테스트에서 실패한다.
