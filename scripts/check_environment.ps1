$ErrorActionPreference = 'Stop'

Write-Host '=== Windows ==='
nvidia-smi --query-gpu=name,driver_version,memory.total --format=csv,noheader
& 'C:\Users\park\Applications\blender-5.2.0-windows-x64\blender.exe' --version | Select-Object -First 1
ollama list | Select-String 'qwen3.8'

Write-Host "`n=== WSL / Pixal3D ==="
wsl -d Ubuntu-24.04 -u park -- /home/park/miniforge3/envs/pixal3d/bin/python -c "import torch; print('torch', torch.__version__, 'cuda', torch.version.cuda); print(torch.cuda.get_device_name(0), torch.cuda.get_device_capability(0))"
wsl -d Ubuntu-24.04 -u park -- /home/park/miniforge3/envs/pixal3d/bin/python -c "import cumesh, flex_gemm, natten, nvdiffrast.torch, o_voxel; print('Pixal3D native extensions: OK')"
