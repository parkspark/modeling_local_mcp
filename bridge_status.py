"""Structured environment checks displayed by the desktop application."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from generation_pipeline import GENERATION_SCRIPT, find_powershell


@dataclass(frozen=True)
class BridgeCheck:
    id: str
    name: str
    ok: bool
    detail: str


def _run(command: list[str], timeout: int = 15) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return False, str(error)

    output = (completed.stdout or completed.stderr).strip()
    first_line = output.splitlines()[0] if output else f"종료 코드 {completed.returncode}"
    return completed.returncode == 0, first_line


def check_powershell() -> BridgeCheck:
    try:
        executable = find_powershell()
    except RuntimeError as error:
        return BridgeCheck("powershell", "PowerShell", False, str(error))
    ok, detail = _run(
        [executable, "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"]
    )
    return BridgeCheck("powershell", "PowerShell", ok, f"v{detail}" if ok else detail)


def check_gpu() -> BridgeCheck:
    executable = shutil.which("nvidia-smi")
    if not executable:
        return BridgeCheck("gpu", "NVIDIA GPU", False, "nvidia-smi를 찾을 수 없음")
    ok, detail = _run(
        [
            executable,
            "--query-gpu=name,memory.total,driver_version",
            "--format=csv,noheader",
        ]
    )
    return BridgeCheck("gpu", "NVIDIA GPU", ok, detail)


def check_wsl() -> BridgeCheck:
    executable = shutil.which("wsl")
    if not executable:
        return BridgeCheck("wsl", "WSL Ubuntu", False, "wsl.exe를 찾을 수 없음")
    ok, detail = _run(
        [executable, "-d", "Ubuntu-24.04", "-u", "park", "--", "printf", "ready"]
    )
    return BridgeCheck(
        "wsl", "WSL Ubuntu", ok, "Ubuntu-24.04 연결됨" if ok else detail
    )


def check_pixal3d() -> BridgeCheck:
    executable = shutil.which("wsl")
    if not executable:
        return BridgeCheck("pixal3d", "Pixal3D", False, "WSL 연결 필요")
    python = "/home/park/miniforge3/envs/pixal3d/bin/python"
    code = (
        "import torch, cumesh, flex_gemm, natten, nvdiffrast.torch, o_voxel; "
        "print('PyTorch ' + torch.__version__ + ' / CUDA ' + str(torch.version.cuda))"
    )
    ok, detail = _run(
        [executable, "-d", "Ubuntu-24.04", "-u", "park", "--", python, "-c", code],
        timeout=30,
    )
    return BridgeCheck("pixal3d", "Pixal3D", ok, detail)


def _blender_candidates() -> list[Path]:
    return [
        Path(r"C:\Users\park\Applications\blender-5.2.0-windows-x64\blender.exe"),
        Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe"),
    ]


def check_blender() -> BridgeCheck:
    blender = next((path for path in _blender_candidates() if path.is_file()), None)
    if blender is None:
        return BridgeCheck("blender", "Blender Bridge", False, "Blender 5.2를 찾을 수 없음")
    ok, detail = _run([str(blender), "--version"], timeout=15)
    return BridgeCheck("blender", "Blender Bridge", ok, detail)


def check_generation_script() -> BridgeCheck:
    ok = GENERATION_SCRIPT.is_file()
    detail = "생성 파이프라인 준비됨" if ok else "generate_model.ps1 누락"
    return BridgeCheck("pipeline", "Generation Bridge", ok, detail)


CHECKS: tuple[Callable[[], BridgeCheck], ...] = (
    check_powershell,
    check_gpu,
    check_wsl,
    check_pixal3d,
    check_blender,
    check_generation_script,
)
