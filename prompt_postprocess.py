"""Convert a constrained Korean/English prompt into safe Blender operations."""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict


COLORS: tuple[tuple[tuple[str, ...], tuple[float, float, float, float]], ...] = (
    (("검은색", "검은", "검정색", "검정", "black"), (0.01, 0.01, 0.01, 1.0)),
    (("흰색", "하얀색", "하양", "white"), (0.95, 0.95, 0.95, 1.0)),
    (("빨간색", "빨강", "red"), (0.8, 0.03, 0.03, 1.0)),
    (("파란색", "파랑", "blue"), (0.03, 0.15, 0.8, 1.0)),
    (("초록색", "녹색", "green"), (0.03, 0.55, 0.12, 1.0)),
    (("회색", "gray", "grey"), (0.35, 0.35, 0.35, 1.0)),
    (("금색", "gold"), (0.83, 0.57, 0.12, 1.0)),
    (("은색", "silver"), (0.65, 0.68, 0.72, 1.0)),
)

TARGET_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("lens", ("안경알", "안경 알", "렌즈", "lens", "glass")),
    ("frame", ("안경테", "안경 테", "프레임", "테", "frame", "rim", "temple")),
)


@dataclass(frozen=True)
class PromptPlan:
    version: int
    source_prompt: str
    operations: list[dict]
    warnings: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _target_for(text: str) -> str:
    lowered = text.lower()
    for target, keywords in TARGET_KEYWORDS:
        if any(keyword in lowered for keyword in keywords):
            return target
    return "all"


def _color_for(text: str) -> tuple[float, float, float, float] | None:
    lowered = text.lower()
    for keywords, color in COLORS:
        if any(keyword in lowered for keyword in keywords):
            return color
    hex_match = re.search(r"#([0-9a-fA-F]{6})\b", text)
    if hex_match:
        value = hex_match.group(1)
        return tuple(int(value[index : index + 2], 16) / 255 for index in (0, 2, 4)) + (1.0,)
    return None


def _percentage(text: str, word: str) -> float | None:
    patterns = (
        rf"(?:{word})\s*(?:를|은|이|로|는)?\s*(\d{{1,3}}(?:\.\d+)?)\s*%",
        rf"(\d{{1,3}}(?:\.\d+)?)\s*%\s*(?:정도\s*)?(?:의\s*)?(?:{word})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return min(100.0, max(0.0, float(match.group(1)))) / 100.0
    return None


def _parse_material_line(line: str) -> dict | None:
    lowered = line.lower()
    operation: dict = {"type": "material", "target": _target_for(line)}
    color = _color_for(line)
    if color:
        operation["base_color"] = list(color)

    if any(word in lowered for word in ("유광", "glossy", "반짝")):
        operation["roughness"] = 0.15
    elif any(word in lowered for word in ("무광", "matte")):
        operation["roughness"] = 0.78

    if any(word in lowered for word in ("금속", "메탈", "metallic", "metal")):
        operation["metallic"] = 0.9
    elif any(word in lowered for word in ("플라스틱", "plastic")):
        operation["metallic"] = 0.0

    opacity = _percentage(lowered, "불투명도|opacity")
    transparency = _percentage(lowered, "투명도|투명|transparency")
    if opacity is not None:
        operation["alpha"] = opacity
    elif transparency is not None:
        operation["alpha"] = 1.0 - transparency
    elif any(word in lowered for word in ("약간 투명", "반투명", "translucent")):
        operation["alpha"] = 0.75

    return operation if len(operation) > 2 else None


def parse_prompt(prompt: str | None) -> PromptPlan:
    source = (prompt or "").strip()
    if not source:
        return PromptPlan(1, "", [], [])

    operations: list[dict] = []
    warnings: list[str] = []
    lines = [line.strip() for line in re.split(r"[\r\n.;]+", source) if line.strip()]
    for line in lines:
        material = _parse_material_line(line)
        if material:
            operations.append(material)

    lowered = source.lower()
    scale_match = re.search(r"(?:전체\s*)?(?:크기|스케일).*?(\d+(?:\.\d+)?)\s*배", lowered)
    if scale_match:
        operations.append(
            {"type": "transform", "target": "all", "scale": float(scale_match.group(1))}
        )
    else:
        percent_scale = re.search(r"(\d+(?:\.\d+)?)\s*%\s*(크게|키워|작게|줄여)", lowered)
        if percent_scale:
            amount = float(percent_scale.group(1)) / 100.0
            scale = 1.0 + amount if percent_scale.group(2) in ("크게", "키워") else 1.0 - amount
            operations.append({"type": "transform", "target": "all", "scale": max(0.01, scale)})

    if any(phrase in lowered for phrase in ("모서리를 둥글", "모서리 둥글", "베벨", "bevel")):
        operations.append(
            {"type": "bevel", "target": "all", "width_ratio": 0.005, "segments": 3}
        )
    if any(phrase in lowered for phrase in ("스무딩", "부드럽게", "smooth shading", "smooth")):
        operations.append({"type": "smooth", "target": "all"})

    reduction = re.search(r"폴리곤.*?(\d+(?:\.\d+)?)\s*%\s*(?:감소|줄)", lowered)
    if reduction:
        ratio = 1.0 - min(99.0, float(reduction.group(1))) / 100.0
        operations.append({"type": "decimate", "target": "all", "ratio": ratio})

    if not operations:
        warnings.append(
            "지원되는 후처리 명령을 찾지 못했습니다. 색상, 유광/무광, 금속성, "
            "투명도, 전체 크기, 베벨, 스무딩 또는 폴리곤 감소를 지정해주세요."
        )
    if any(operation.get("target") != "all" for operation in operations):
        warnings.append(
            "부위 지정은 생성된 오브젝트나 재질 이름에 lens/frame 같은 의미 있는 이름이 "
            "있을 때만 정확히 적용됩니다."
        )
    return PromptPlan(1, source, operations, warnings)
