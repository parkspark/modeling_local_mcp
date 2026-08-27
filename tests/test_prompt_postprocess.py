import pytest

from prompt_postprocess import parse_prompt


def test_parses_glossy_black_frame_and_transparent_lens():
    plan = parse_prompt(
        "안경 테는 유광의 검은 재질\n안경 알은 검은색이고 20%정도 투명도"
    )

    frame = next(operation for operation in plan.operations if operation["target"] == "frame")
    lens = next(operation for operation in plan.operations if operation["target"] == "lens")
    assert frame["roughness"] == pytest.approx(0.15)
    assert frame["base_color"][:3] == pytest.approx([0.01, 0.01, 0.01])
    assert lens["alpha"] == pytest.approx(0.8)


def test_parses_scale_bevel_smooth_and_decimate():
    plan = parse_prompt(
        "전체 크기를 1.2배로 하고 모서리를 둥글게, 부드럽게 해줘. 폴리곤 30% 감소"
    )
    operation_types = {operation["type"] for operation in plan.operations}
    assert {"transform", "bevel", "smooth", "decimate"} <= operation_types


def test_unknown_prompt_has_warning_and_no_operations():
    plan = parse_prompt("좀 더 미래적으로 만들어줘")
    assert not plan.operations
    assert plan.warnings


def test_hex_color_and_matte_material():
    plan = parse_prompt("전체를 #336699 무광 재질로")
    operation = plan.operations[0]
    assert operation["roughness"] == pytest.approx(0.78)
    assert operation["base_color"][:3] == pytest.approx([0.2, 0.4, 0.6])
