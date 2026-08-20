# 설치 상태 기록 (2026-08-19)

## 하드웨어 및 런타임

- GPU: NVIDIA GeForce RTX 5090, 32GB, compute capability 12.0
- Windows NVIDIA driver: 610.62
- WSL: Ubuntu 24.04
- Conda environment: `/home/park/miniforge3/envs/pixal3d`
- Python: 3.10.20
- CUDA compiler: 13.0.48
- PyTorch: 2.10.0+cu130
- TorchVision: 0.25.0+cu130
- Blender: 5.2.0 LTS portable
- WSL memory limit: 52GB, swap 16GB (`C:\Users\park\.wslconfig`)

## 소스 고정값

- Pixal3D: `cdbb2bbffbf4e6f298b5f2af3d1d76a8d823d2af`
- TRELLIS.2: `75fbf0183001ed9876c8dbb35de6b68552ee08bd`
- nvdiffrast 0.4.0: `253ac4fcea7de5f396371124af597e6cc957bfae`
- nvdiffrec renderutils: `b296927cc7fd01c2ac1087c8065c4d7248f72da4`
- CuMesh: `12289e1062f0603f2f0d0771b02e1395d247f26f`
- FlexGEMM: `6dd94a859c26ee8246888502eada3dd8ad85532e`
- NATTEN: 0.21.0, CUDA architecture 12.0 로컬 빌드
- Background removal: public `ZhengPeng7/BiRefNet` (Pixal3D config의 gated RMBG-2.0 대체 패치 적용)

## UniRig 사람형 자동 리깅

- UniRig: `6793c6640ff01c8fb389f3993434124bb43d2933`
- 위치: `/home/park/local-modeling/UniRig`
- Conda environment: `/home/park/miniforge3/envs/unirig`
- Python: 3.11.15
- PyTorch: 2.10.0+cu130
- TorchVision: 0.25.0+cu130
- spconv: `spconv-cu126==2.3.8`
- torch-scatter: 2.1.2, CUDA 13 / SM 12.0 로컬 빌드
- torch-cluster: 1.6.3, CUDA 13 / SM 12.0 로컬 빌드
- Attention: FlashAttention 대신 PyTorch SDPA 호환 패치
- Model cache: `/home/park/.cache/huggingface/hub/models--VAST-AI--UniRig`

## CUDA 레이아웃 보정

Conda CUDA Toolkit의 헤더와 라이브러리가 `targets/x86_64-linux` 아래에 있으므로 `/home/park/cuda-13`에 표준 CUDA 레이아웃을 가리키는 심볼릭 링크를 구성했습니다. WSL 드라이버의 `libcuda.so`도 이 링크 경로에서 찾도록 연결했습니다.

## 모델 캐시

Hugging Face 캐시 위치는 `/home/park/.cache/huggingface`입니다. Pixal3D 체크포인트만 약 22.4GB이며, 첫 설치 시 DINOv3·MoGe-2·NAF 가중치가 추가로 다운로드됩니다.

현재 내려받은 `TencentARC/Pixal3D` 모델 저장소의 LICENSE는 MIT입니다. 다만 DINOv3·MoGe-2·NAF 같은 업스트림 모델, 입력 이미지, 학습 데이터 및 생성 결과물의 권리는 별개일 수 있으므로 상업 배포 전에는 각 모델 카드와 NOTICE를 다시 확인해야 합니다.
