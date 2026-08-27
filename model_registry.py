"""Models exposed by the local image-to-3D GUI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelDefinition:
    id: str
    display_name: str
    description: str
    supports_prompt: bool
    handler: str


MODELS: dict[str, ModelDefinition] = {
    "pixal3d-1024": ModelDefinition(
        id="pixal3d-1024",
        display_name="Pixal3D 1024 (이미지 → 3D)",
        description=(
            "RTX 5090용 저메모리 모드로 GLB를 생성하고, BLEND와 FBX로 변환합니다. "
            "현재 설치된 Pixal3D는 텍스트 프롬프트를 직접 지원하지 않습니다."
        ),
        supports_prompt=False,
        handler="powershell_pixal3d",
    ),
}


def model_choices() -> list[tuple[str, str]]:
    """Return Gradio-compatible (label, value) choices."""
    return [(model.display_name, model.id) for model in MODELS.values()]


def describe_model(model_id: str) -> str:
    model = MODELS[model_id]
    prompt_badge = "프롬프트 직접 지원" if model.supports_prompt else "프롬프트 직접 지원 안 함"
    return f"**{prompt_badge}**  \n{model.description}"
