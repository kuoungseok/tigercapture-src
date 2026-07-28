# Motion Designer - Painter 연동 TODO

상태: **제품 템플릿 작업 이후로 연기**

현재 코드에는 Painter UI 객체를 Motion Designer에서 편집하는 브리지와
`.tgmotion`을 Painter의 `motion_actor`로 배치하는 실험 경로가 있다. 이 경로는
삭제하지 않지만, 아래 항목이 끝나기 전에는 완성된 Painter 연동으로 주장하지
않는다.

## 남은 작업

- Painter Media/Assets 패널에서 `.tgmotion` 썸네일과 길이 표시
- 파일 선택뿐 아니라 Assets에서 캔버스로 드래그 앤 드롭
- 여러 Motion Actor의 독립 재생 헤드, 시작 오프셋, 반복 구간
- Painter 변형과 Motion 내부 카메라/좌표계의 명확한 합성 규칙
- GPU 프레임 공유로 Painter 미리보기의 CPU 프레임 생성 제거
- 누락된 이미지, 폰트, 음향 리소스의 재연결 UI
- `.tspaint` 패키지에 외부 Motion 의존 리소스를 포함하는 수집 정책
- Motion 변경 감지, 자동 재로딩, 충돌 해결
- Painter 정지 화면·영상 출력과 Motion Designer 출력의 픽셀 parity
- Undo/Redo, 복제, 그룹화, 삭제 후 고아 컴포지션 정리
- AI/MCP 배치, 재연결, 재생 범위, 프레임 캡처 액션
- 실제 긴 UI/광고/교육 템플릿을 사용한 성능 및 사용성 QA

## 재개 조건

Motion 템플릿 갤러리에 실제 제작 시작점이 되는 UI, 광고, 교육 템플릿이
충분히 갖춰지고, 최소 15초·30초·60초 다중 장면 프로젝트가 Preview/Export
회귀 검사를 통과한 뒤 연동 폴리싱을 재개한다.
