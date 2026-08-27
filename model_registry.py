"""Models exposed by the local image-to-3D GUI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelDefinition:
    id: str
    display_name: str
    description: str
    supports_prompt: bool
    supports_postprocess_prompt: bool
    handler: str


MODELS: dict[str, ModelDefinition] = {
    "pixal3d-1024": ModelDefinition(
        id="pixal3d-1024",
        display_name="Pixal3D 1024 (이미지 → 3D)",
        description=(
            "RTX 5090용 저메모리 모드로 GLB를 생성하고, BLEND와 FBX로 변환합니다. "
            "Pixal3D 생성 후 Blender에서 지원되는 재질·형상 프롬프트를 적용합니다."
        ),
        supports_prompt=False,
        supports_postprocess_prompt=True,
        handler="powershell_pixal3d",
    ),
}


def model_choices() -> list[tuple[str, str]]:
    """Return Gradio-compatible (label, value) choices."""
    return [(model.display_name, model.id) for model in MODELS.values()]


def describe_model(model_id: str) -> str:
    model = MODELS[model_id]
    if model.supports_prompt:
        prompt_badge = "프롬프트 직접 지원"
    elif model.supports_postprocess_prompt:
        prompt_badge = "Blender 후처리 프롬프트 지원"
    else:
        prompt_badge = "프롬프트 지원 안 함"
    return f"**{prompt_badge}**  \n{model.description}"
