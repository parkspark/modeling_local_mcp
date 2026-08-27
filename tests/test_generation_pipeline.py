from pathlib import Path
from unittest.mock import patch

import pytest

import generation_pipeline as pipeline
from model_registry import MODELS, describe_model, model_choices


def test_model_registry_exposes_pixal3d():
    assert "pixal3d-1024" in MODELS
    assert model_choices()[0][1] == "pixal3d-1024"
    assert "프롬프트 직접 지원 안 함" in describe_model("pixal3d-1024")


def test_validate_image_accepts_supported_extension(tmp_path: Path):
    image = tmp_path / "sample.PNG"
    image.write_bytes(b"not-decoded-by-this-layer")
    assert pipeline.validate_image(image) == image.resolve()


def test_validate_image_rejects_unsupported_extension(tmp_path: Path):
    image = tmp_path / "sample.txt"
    image.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="지원하지 않는"):
        pipeline.validate_image(image)


def test_create_job_copies_input_and_records_unapplied_prompt(tmp_path: Path):
    image = tmp_path / "sample.png"
    image.write_bytes(b"image")
    artifacts = tmp_path / "artifacts"

    with patch.object(pipeline, "ARTIFACTS_DIRECTORY", artifacts):
        request, copied, job_directory = pipeline.create_job(
            image, "pixal3d-1024", "make it round"
        )

    assert copied.read_bytes() == b"image"
    assert request.prompt == "make it round"
    metadata = (job_directory / "request.json").read_text(encoding="utf-8")
    assert '"prompt_applied_directly": false' in metadata


def test_build_command_keeps_paths_as_individual_arguments(tmp_path: Path):
    image = tmp_path / "image with spaces.png"
    with patch.object(pipeline, "find_powershell", return_value="powershell.exe"):
        command = pipeline.build_command(image, "gui-test")

    assert command[-6:-2] == ["-Image", str(image), "-Name", "gui-test"]
    assert command[-2:] == ["-ArtifactRoot", str(pipeline.ARTIFACTS_DIRECTORY)]
