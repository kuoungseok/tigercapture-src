# Spine 에디터 — 진행 상황 및 미결 이슈

## 완료된 작업

### 바이너리 파서 (spine_json_parser.py)
- UTF-8 BOM 처리: `utf-8-sig` 인코딩 → Nikke atlas 파일명 오류 수정
- Spine 3.8 binary 슬롯 파싱:
  - color: raw 4바이트 (varint 아님)
  - dark color: raw 4바이트
  - attachment name: string table index (`idx-1`, 1-indexed)
- `_read_bstr()`: multi-byte varint 문자열 길이 지원 (긴 한국어 경로 수정)
- String table 3.8 포맷 (`n=strings[n-1]` 규칙, 공식 C++ 소스 확인)
- 블루아카이브 기본 스킨 synthesize (slot attachment → RegionAttachment)

### 본 트랜스폼 (spine_data.py)
- 전체 재작성: shear_x/y, transform_mode 추가
- 5가지 transform mode 구현 (spine-csharp Bone.cs 기준):
  - Normal, OnlyTranslation, NoRotationOrReflection, NoScale, NoScaleOrReflection
- apply_animation(): scale += (v-1), shear 지원
- store_bind_pose(): shear 포함

### GL 렌더러 (spine_gl_renderer.py)
- 셰이더 `#version 120` → `#version 330 core`
- `beginNativePainting()` / `endNativePainting()` 패턴으로 수정
- mesh 가중치 `bi=-1` 버그 수정 (마지막 본 대신 슬롯 본 사용)
- `_fit_skeleton()`: 극단값 뼈 필터링, bi=-1 버그 수정
- GL 텍스처 deferred destroy (컨텍스트 없이 해제하는 크래시 방지)
- 크로스헤어 OverflowError 방지 (±32000 clamp)

### CPU 렌더러 (spine_renderer.py)
- atlas rotate=true 크롭 버그 수정: `(rx, ry, rx+rh, ry+rw)` (너비/높이 swap)
- linkedmesh UV 수정: 부모 UV를 덮어쓰지 않고 자신의 UV 유지
- 파서에서 shearX/Y, transform mode 읽기 추가

### 에디터 창 (editor_window.py)
- 탐색기: 폴더 트리 + 파일 그리드 (Windows 탐색기 스타일)
- .skel 바이너리 형식 지원
- atlas 이름 유연한 매칭 (파일명이 다를 때 폴더 내 .atlas 자동 탐색)
- 자동 스킨 선택: default가 비어있으면 첫 캐릭터 스킨 선택

---

## 미결 이슈

### 1. chibi-stickers / mix-and-match GL 렌더링 안 됨
**증상:** GL 뷰포트에 십자 마크만 보임
**원인:** `load_atlas_pages()` 가 다중 페이지 atlas(탭 들여쓰기 형식)에서 첫 번째 페이지만 반환
- chibi-stickers atlas는 탭(`\t`) 들여쓰기 Spine v4 형식
- 현재 파서가 두 번째 이후 이미지 파일명을 page header로 인식 못 함
- **수정 방향:** `load_atlas_pages()` 에서 `\t` 들여쓰기 atlas도 page 감지하도록
- CPU 렌더러로 렌더는 정상 작동함 (erikari 스킨 선택 시)

### 2. 블루아카이브 파츠 위치
**증상:** PC_Layer 본이 world_y=-1000에 있어 모든 파츠가 화면 아래로 몰림
**원인:** 블루아카이브 face-tracking 스프라이트는 뼈 3개(root/PC_Layer/halo) 구조라
뷰포트 auto-fit이 이상하게 잡힘
**수정 방향:** viewport fit 시 attachment 실제 크기 기반으로 center 계산

### 3. Nikke GL 렌더링 얼굴/눈 순서
**증상:** 얼굴 메시가 눈 위에 렌더링됨
**원인:** 이전 `bi=-1` 버그 수정 후 개선됐으나 완전히 해결됐는지 미확인
**수정 방향:** 사용자 재확인 필요

### 4. mix-and-match 다중 스킨 조합
**증상:** 단일 스킨으로는 완전한 캐릭터 불가
**원인:** mix-and-match는 `full-skins/girl` + `hair/blue` + `clothes/dress` 등 여러 스킨 조합이 필요
**수정 방향:** 다중 스킨 merge UI 추가 필요

---

## 참고
- NikkeViewerEX: removed from the workspace after extracting the needed test notes.
- SpineSkeletonDataConverter: https://github.com/wang606/SpineSkeletonDataConverter
  - `SkeletonData38BinaryReader.cpp`: 3.8 binary 파싱 정확한 C++ 구현
  - `readStringRef`: `index-1` (1-indexed), 0=null

---

## 2026-07-02 UI / Review Guardrail

- Main editor UI renewal and review automation may show Spine/NIKKE only as
  actor-track and compatibility-management surfaces until renderer correctness
  is proven with real pixels.
- Do not claim Spine visual readiness from action automation, nonblank renders,
  generated catalog images, or placeholder actor cards.
- Do not use Spine/NIKKE as product-facing success evidence when any of these
  are visible: misplaced face parts, missing hands/arms, deformed weighted
  meshes, incorrect draw order, broken multi-page atlas textures, or
  chibi-stickers cross-marker output.
- Review PPT/HTML/catalog automation must treat Spine captures as WIP evidence
  unless a real editor or Spine viewer capture passes visual review for the
  specific sample being presented.
- Keep Spine menu/library/loading-manager access available for developer QA,
  but hold back "visual ready" copy and detailed Spine feature slides until the
  separate renderer work is fixed.
- Spine 공식 C# 런타임: `Bone.UpdateWorldTransform()` 참고
