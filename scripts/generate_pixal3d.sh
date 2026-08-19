#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: generate_pixal3d.sh INPUT_IMAGE OUTPUT_GLB [SEED] [LOG_FILE]" >&2
  exit 2
fi

input_image="$1"
output_glb="$2"
seed="${3:-42}"
log_file="${4:-$(dirname "$output_glb")/pixal3d.log}"

env_prefix="/home/park/miniforge3/envs/pixal3d"
pixal_dir="/home/park/local-modeling/Pixal3D"

export CUDA_HOME="/home/park/cuda-13"
export PATH="$env_prefix/bin:$PATH"
export PYTHONPATH="$pixal_dir:${PYTHONPATH:-}"
export ATTN_BACKEND="sdpa"
export SPARSE_ATTN_BACKEND="sdpa"
export SPARSE_CONV_BACKEND="flex_gemm"
export PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"
export HF_HOME="/home/park/.cache/huggingface"
export HF_HUB_DISABLE_XET="1"
export TORCH_HOME="/home/park/.cache/torch"
export PIXAL_REMBG_MODEL="ZhengPeng7/BiRefNet"
export PYTHONUNBUFFERED="1"

mkdir -p "$(dirname "$output_glb")"
mkdir -p "$(dirname "$log_file")"
exec > >(tee -a "$log_file") 2>&1
cd "$pixal_dir"

started_at="$(date +%s)"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pixal3D job starting"
echo "[CONFIG] input=$input_image"
echo "[CONFIG] output=$output_glb"
echo "[CONFIG] seed=$seed resolution=1024 low_vram=true"
echo "[CONFIG] python=$($env_prefix/bin/python --version 2>&1)"
echo "[CONFIG] cuda_home=$CUDA_HOME"
if [[ -f "$input_image" ]]; then
  echo "[INPUT] $(file "$input_image")"
  echo "[INPUT] size_bytes=$(stat -c '%s' "$input_image")"
else
  echo "[ERROR] Input image does not exist: $input_image"
  exit 3
fi
if command -v nvidia-smi >/dev/null 2>&1; then
  echo "[GPU] $(nvidia-smi --query-gpu=name,driver_version,memory.total,memory.used --format=csv,noheader,nounits | head -n 1)"
fi

"$env_prefix/bin/python" -u inference.py \
  --image "$input_image" \
  --output "$output_glb" \
  --seed "$seed" \
  --low_vram \
  --resolution 1024 &
python_pid=$!

while kill -0 "$python_pid" 2>/dev/null; do
  elapsed=$(( $(date +%s) - started_at ))
  gpu_status="unavailable"
  if command -v nvidia-smi >/dev/null 2>&1; then
    gpu_status="$(nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader,nounits | head -n 1)"
  fi
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ALIVE] pid=$python_pid elapsed=${elapsed}s gpu_util,vram_used,vram_total,temp=$gpu_status"
  sleep 15
done

set +e
wait "$python_pid"
exit_code=$?
set -e
elapsed=$(( $(date +%s) - started_at ))
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Pixal3D job finished exit_code=$exit_code elapsed=${elapsed}s"
if [[ $exit_code -eq 0 && -f "$output_glb" ]]; then
  echo "[OUTPUT] size_bytes=$(stat -c '%s' "$output_glb") path=$output_glb"
fi
exit "$exit_code"
