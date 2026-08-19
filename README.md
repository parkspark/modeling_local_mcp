https://youtu.be/qapRggMK534



# 로컬 이미지 → 편집 가능한 3D 에셋 환경

이 PC의 RTX 5090(32GB)에 맞춰 **Pixal3D 1024 저메모리 모드**를 기본 생성기로 사용합니다. 입력 사진 한 장에서 PBR 텍스처가 포함된 GLB를 만들고, Blender를 통해 편집 가능한 `.blend`와 Unity/Unreal 등에서 쓸 `.fbx`도 함께 생성합니다.

## 바로 사용하기

PowerShell에서 다음을 실행합니다.

```powershell
cd ..\local_modeling_mcp
.\scripts\generate_model.ps1 -Image .\inputs\chair.png -Name chair
```

출력은 `artifacts\chair\`에 생깁니다.

- `chair.glb`: PBR 재질 보존이 가장 좋은 원본. Unity에서는 glTFast 같은 GLTF 임포터 사용 권장
- `chair.blend`: Blender에서 메시, UV, 재질을 직접 수정하는 작업 파일
- `chair.fbx`: Unity/Unreal의 기본 임포터용 교환 파일

기존 GLB만 변환하려면 다음을 실행합니다.

```powershell
.\scripts\convert_model.ps1 -InputGlb C:\path\asset.glb
```

영상은 우선 일정 간격의 키 프레임으로 나눈 뒤 가장 형태가 잘 보이는 프레임을 생성 입력으로 사용합니다.

```powershell
.\scripts\extract_video_frames.ps1 -Video C:\path\turntable.mp4 -EverySeconds 2
```

환경 점검:

```powershell
.\scripts\check_environment.ps1
```

## 설치 위치와 고정 구성
*park 은 사용자 이름으로 변경해야함

- WSL: Ubuntu 24.04, 사용자 `park`
- Conda: `/home/park/miniforge3/envs/pixal3d`
- CUDA compatibility path: `/home/park/cuda-13`
- Pixal3D: `/home/park/local-modeling/Pixal3D`
- TRELLIS.2 및 CUDA 확장 소스: `/home/park/local-modeling/TRELLIS.2`
- Blender 포터블: `C:\Users\park\Applications\blender-5.2.0-windows-x64`
- Attention: FlashAttention 대신 RTX 5090에서 호환성이 높은 PyTorch SDPA
- 생성 해상도: 1024, low-VRAM 모드


## 입력 사진 팁

- 물체 하나를 화면 중앙에 크게 두고 배경과 경계를 분명하게 합니다.
- 가려진 뒷면은 모델이 추정하므로 정면·측면 정보가 함께 드러나는 3/4 시점이 유리합니다.
- 여러 시점이나 영상은 우선 선명한 키 프레임을 추출한 뒤 각 결과를 비교하는 워크플로가 안정적입니다.
- 텍스트만으로 만들 때는 클라우드 모델로 콘셉트 이미지를 만든 뒤 그 이미지를 입력하는 2단계 방식을 사용합니다.

## 엔진 이식 주의사항

GLB는 PBR 텍스처를 가장 잘 보존합니다. FBX는 엔진과 재질 체계에 따라 metallic/roughness 연결을 다시 잡아야 할 수 있습니다. 게임 투입 전에는 Blender에서 폴리곤 감축, UV 확인, 실제 크기 적용, 피벗 설정, 충돌 메시와 LOD 생성을 권장합니다.

Pixal3D 코드와 각 체크포인트·의존성은 서로 다른 라이선스를 가질 수 있습니다. 특히 상업 배포 전에는 사용한 체크포인트의 Hugging Face 라이선스와 데이터/에셋 권리를 별도로 확인해야 합니다.

정확한 버전과 커밋은 `docs\environment-lock.md`에 기록되어 있습니다.
