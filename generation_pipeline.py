"""Safe subprocess bridge between the GUI and the existing PowerShell pipeline."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from queue import Empty, Queue
from typing import Iterator
from uuid import uuid4

from model_registry import MODELS
from prompt_postprocess import parse_prompt


SOURCE_ROOT = Path(__file__).resolve().parent
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", SOURCE_ROOT))
DATA_ROOT = (
    Path.home() / "Documents" / "Local3DModelingStudio"
    if getattr(sys, "frozen", False)
    else SOURCE_ROOT
)
ARTIFACTS_DIRECTORY = DATA_ROOT / "artifacts"
GENERATION_SCRIPT = RESOURCE_ROOT / "scripts" / "generate_model.ps1"
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass(frozen=True)
class GenerationRequest:
    job_id: str
    model_id: str
    prompt: str
    source_image_name: str
    created_at: str


@dataclass(frozen=True)
class GenerationResult:
    job_id: str
    artifact_directory: Path
    files: list[Path]
    exit_code: int


def validate_image(image_path: str | os.PathLike[str] | None) -> Path:
    if not image_path:
        raise ValueError("먼저 생성에 사용할 이미지를 선택해주세요.")

    resolved = Path(image_path).expanduser().resolve()
    if not resolved.is_file():
        raise ValueError("선택한 이미지 파일을 찾을 수 없습니다.")
    if resolved.suffix.lower() not in ALLOWED_IMAGE_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_IMAGE_EXTENSIONS))
        raise ValueError(f"지원하지 않는 이미지 형식입니다. 사용 가능 형식: {allowed}")
    return resolved


def create_job(
    image_path: str | os.PathLike[str], model_id: str, prompt: str | None
) -> tuple[GenerationRequest, Path, Path]:
    source = validate_image(image_path)
    if model_id not in MODELS:
        raise ValueError("선택한 모델이 모델 레지스트리에 없습니다.")

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    job_id = f"gui-{timestamp}-{uuid4().hex[:8]}"
    artifact_directory = ARTIFACTS_DIRECTORY / job_id
    artifact_directory.mkdir(parents=True, exist_ok=False)

    copied_image = artifact_directory / f"input{source.suffix.lower()}"
    shutil.copy2(source, copied_image)

    request = GenerationRequest(
        job_id=job_id,
        model_id=model_id,
        prompt=(prompt or "").strip(),
        source_image_name=source.name,
        created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
    )
    postprocess_plan = parse_prompt(request.prompt)
    metadata = {
        **asdict(request),
        "prompt_applied_directly": bool(
            request.prompt and MODELS[model_id].supports_prompt
        ),
        "prompt_postprocess_supported": MODELS[model_id].supports_postprocess_prompt,
        "postprocess_operation_count": len(postprocess_plan.operations),
    }
    (artifact_directory / "request.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (artifact_directory / "postprocess_plan.json").write_text(
        json.dumps(postprocess_plan.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return request, copied_image, artifact_directory


def find_powershell() -> str:
    for executable in ("pwsh", "powershell"):
        discovered = shutil.which(executable)
        if discovered:
            return discovered
    raise RuntimeError("PowerShell 실행 파일을 찾을 수 없습니다.")


def build_command(
    image_path: Path, job_id: str, postprocess_plan: Path | None = None
) -> list[str]:
    command = [
        find_powershell(),
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(GENERATION_SCRIPT),
        "-Image",
        str(image_path),
        "-Name",
        job_id,
        "-ArtifactRoot",
        str(ARTIFACTS_DIRECTORY),
    ]
    if postprocess_plan is not None:
        command.extend(["-PostprocessPlan", str(postprocess_plan)])
    return command


def _read_stream(stream, label: str, output_queue: Queue[tuple[str, str | None]]) -> None:
    try:
        for line in iter(stream.readline, ""):
            output_queue.put((label, line.rstrip("\r\n")))
    finally:
        stream.close()
        output_queue.put((label, None))


def stream_generation(
    image_path: str | os.PathLike[str], model_id: str, prompt: str | None
) -> Iterator[tuple[str, GenerationResult | None]]:
    request, copied_image, artifact_directory = create_job(
        image_path, model_id, prompt
    )
    model = MODELS[model_id]
    gui_log_path = artifact_directory / "gui.log"

    initial_lines = [
        f"[GUI] 작업 생성: {request.job_id}",
        f"[GUI] 모델: {model.display_name}",
        f"[GUI] 입력 이미지: {copied_image}",
    ]
    plan_path = artifact_directory / "postprocess_plan.json"
    plan = parse_prompt(request.prompt)
    if request.prompt and model.supports_postprocess_prompt:
        initial_lines.append(
            f"[GUI] Blender 후처리 명령 {len(plan.operations)}개를 생성했습니다."
        )
        for operation in plan.operations:
            initial_lines.append(f"[POSTPROCESS][PLAN] {json.dumps(operation, ensure_ascii=False)}")
        for warning in plan.warnings:
            initial_lines.append(f"[POSTPROCESS][WARN] {warning}")
    elif request.prompt and not model.supports_prompt:
        initial_lines.append("[안내] 이 모델에서는 입력한 프롬프트가 적용되지 않습니다.")
    elif request.prompt:
        initial_lines.append("[GUI] 프롬프트를 모델에 전달합니다.")
    else:
        initial_lines.append("[GUI] 프롬프트 없이 이미지 기반 생성을 시작합니다.")

    accumulated = "\n".join(initial_lines) + "\n"
    gui_log_path.write_text(accumulated, encoding="utf-8")
    yield accumulated, None

    if model.handler != "powershell_pixal3d":
        raise RuntimeError(f"구현되지 않은 모델 핸들러입니다: {model.handler}")

    command = build_command(copied_image, request.job_id, plan_path)
    process = subprocess.Popen(
        command,
        cwd=DATA_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert process.stdout is not None
    assert process.stderr is not None

    output_queue: Queue[tuple[str, str | None]] = Queue()
    readers = [
        threading.Thread(
            target=_read_stream, args=(process.stdout, "OUT", output_queue), daemon=True
        ),
        threading.Thread(
            target=_read_stream, args=(process.stderr, "ERR", output_queue), daemon=True
        ),
    ]
    for reader in readers:
        reader.start()

    finished_streams = 0
    with gui_log_path.open("a", encoding="utf-8") as log_file:
        while finished_streams < len(readers):
            try:
                label, line = output_queue.get(timeout=0.25)
            except Empty:
                continue
            if line is None:
                finished_streams += 1
                continue
            rendered = f"[{label}] {line}"
            accumulated += rendered + "\n"
            log_file.write(rendered + "\n")
            log_file.flush()
            yield accumulated, None

    exit_code = process.wait()
    if exit_code != 0:
        failure = f"[오류] 생성 프로세스가 종료 코드 {exit_code}로 실패했습니다."
        accumulated += failure + "\n"
        with gui_log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(failure + "\n")
        yield accumulated, GenerationResult(
            request.job_id, artifact_directory, [gui_log_path], exit_code
        )
        return

    expected_files = [
        artifact_directory / f"{request.job_id}.glb",
        artifact_directory / f"{request.job_id}.blend",
        artifact_directory / f"{request.job_id}.fbx",
    ]
    missing = [path.name for path in expected_files if not path.is_file()]
    if missing:
        failure = "[오류] 생성은 종료됐지만 결과 파일이 없습니다: " + ", ".join(missing)
        accumulated += failure + "\n"
        with gui_log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(failure + "\n")
        yield accumulated, GenerationResult(
            request.job_id, artifact_directory, [gui_log_path], 1
        )
        return

    result_files = expected_files + [
        artifact_directory / "request.json",
        plan_path,
        gui_log_path,
    ]
    pixal_logs = sorted(artifact_directory.glob("pixal3d-*.log"))
    result_files.extend(pixal_logs)
    accumulated += f"[완료] 결과 저장 위치: {artifact_directory}\n"
    yield accumulated, GenerationResult(
        request.job_id, artifact_directory, result_files, 0
    )
