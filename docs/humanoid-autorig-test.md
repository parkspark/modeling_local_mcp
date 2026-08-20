# 사람형 자동 리깅 1차 테스트

테스트 날짜: 2026-08-20

## 결과

`melting_knight.glb`를 UniRig로 골격 예측·스키닝한 뒤 Blender에서 Unity Humanoid 이름으로 정규화했다.

| 검사 | 결과 |
| --- | --- |
| UniRig 기준 모델 골격 | PASS — 44 bones |
| UniRig 기준 모델 스키닝 | PASS — 미웨이트 정점 0, 최대 영향 본 4 |
| melting_knight 골격 | PASS — 34 bones |
| melting_knight 스키닝 | PASS — 775,469/775,469 정점 웨이트 보유 |
| Blender Armature 연결 | PASS — Armature modifier 및 버텍스 그룹 34/34 일치 |
| Unity Humanoid Avatar | PASS — `isHuman=true`, `isValid=true` |
| Unity 필수 본 | PASS — 누락 0, Humanoid 매핑 33개 |
| Unity 근육 포즈 변형 | PASS — 근육 4개 적용, 최대 정점 이동 약 0.30m |
| 육안 변형 품질 | WARN — 갑옷 치맛단과 녹은 장식이 다리와 함께 늘어남 |

자동 리깅과 Unity 리타게팅 기반은 성립했다. 다만 현재 생성 모델은 갑옷·천·녹은 장식이 신체와 하나의 고해상도 메시로 붙어 있어 게임 투입 전 메시 분리, 리토폴로지, 웨이트 보정이 필요하다.

## 실행

```powershell
cd C:\Users\park\Desktop\dev_tool\modeling_local_mcp
.\scripts\rig_humanoid.ps1 `
  -InputGlb .\artifacts\melting_knight\melting_knight.glb `
  -Name melting_knight
```

결과는 입력 모델 옆의 `rigged` 폴더에 생성된다.

- `melting_knight_humanoid.fbx`: Unity Humanoid 입력용
- `melting_knight_humanoid.blend`: 본과 웨이트 수정용
- `melting_knight_rigged.glb`: 원본 텍스처와 리그가 병합된 중간 결과
- `rig_report.json`: 본 매핑과 정점 웨이트 구조 검사
- `rest_preview.png`, `pose_preview.png`: 육안 비교 렌더

## 로컬 환경

- UniRig commit: `6793c6640ff01c8fb389f3993434124bb43d2933`
- 위치: `/home/park/local-modeling/UniRig`
- Conda: `/home/park/miniforge3/envs/unirig`
- Python 3.11
- PyTorch 2.10.0+cu130
- `spconv-cu126==2.3.8`
- `torch-scatter==2.1.2`: CUDA 13 / SM 12.0 소스 빌드
- `torch-cluster==1.6.3`: CUDA 13 / SM 12.0 소스 빌드
- UniRig 체크포인트 캐시: `/home/park/.cache/huggingface/hub/models--VAST-AI--UniRig`

RTX 5090에서 FlashAttention 소스 빌드는 병렬 CUDA 컴파일 중 WSL 메모리를 초과했다. 대신 다음 패치를 적용해 공식 체크포인트의 파라미터 이름을 유지하면서 PyTorch SDPA로 실행한다.

- `patches/unirig_cuda13_sdpa.patch`
- `patches/unirig_pytorch210_safe_checkpoint.patch`

두 번째 패치는 VAST-AI 공식 체크포인트 안의 `python-box` 설정 객체 때문에 PyTorch 2.6+의 weights-only 로더가 실패하는 문제를 처리한다. 체크포인트 출처를 공식 Hugging Face 저장소로 고정한 환경에서만 사용한다.

## Unity 검증 위치

- 프로젝트: `C:\Users\park\My project (61)`
- FBX: `Assets\AutoRigTest\melting_knight_humanoid.fbx`
- 검증기: `Assets\Editor\AutoRigTestImporter.cs`
- 결과: `AutoRigTestResults\unity_validation.json`

검증기는 씬을 저장하거나 변경하지 않는다. FBX를 `Human / Create From This Model`로 임포트하고 임시 인스턴스에 `HumanPoseHandler` 근육 값을 적용한 뒤 BakeMesh 전후 정점 이동을 측정한다.

## 현재 제한

- 후처리기는 Hips 아래 척추 1개와 다리 2개가 분기되고, UpperChest에서 목과 양팔이 분기되는 이족보행 계층을 대상으로 한다.
- UniRig 업스트림 실행기는 공백이 있는 경로를 안전하게 처리하지 못하므로 통합 스크립트가 해당 경로를 거부한다.
- 얼굴 리그는 포함하지 않는다.
- 손은 모델이 예측한 엄지·중지 계열만 매핑됐다.
- 원본이 77만 정점이므로 실시간 게임용으로는 과도하다.

## 다음 단계

1. 몸, 단단한 갑옷, 치맛단·녹은 장식을 별도 메시 또는 별도 웨이트 영역으로 분리한다.
2. 50k~100k 삼각형 수준의 애니메이션용 리토폴로지를 만든다.
3. 어깨, 골반, 치맛단 웨이트를 수동 보정한다.
4. 표준 Idle/Walk 클립으로 발 미끄러짐과 관절 관통을 검증한다.

## 2차 테스트: T-pose 입력

`melting_knight_tpose.png`를 정면 대칭 T-pose로 새로 생성하고, 긴 용융 장식과 팔다리를 잇는 요소를 제거한 뒤 같은 Pixal3D → UniRig → Unity 파이프라인을 실행했다.

| 검사 | 결과 |
| --- | --- |
| 자동 리깅 | PASS — 52 bones |
| 스키닝 | PASS — 736,923/736,923 정점 웨이트 보유, 최대 영향 본 4 |
| Unity Humanoid Avatar | PASS — `isHuman=true`, `isValid=true` |
| Unity 필수 본 | PASS — 누락 0, Humanoid 매핑 52개 |
| Unity 근육 포즈 변형 | PASS — 근육 4개 적용, 최대 정점 이동 약 0.369m |
| 육안 변형 품질 | PASS/WARN — 1차의 하체 늘어짐은 제거됨. 어깨판과 허리 판금은 강체 웨이트 보정 권장 |

결과 파일은 `artifacts/melting_knight_tpose/rigged`에 있으며 Unity 검증 모델은 `Assets/AutoRigTest/melting_knight_tpose_humanoid.fbx`다. T-pose와 단순한 대칭 실루엣이 자동 골격 추정 및 변형 품질을 실제로 개선했다.
