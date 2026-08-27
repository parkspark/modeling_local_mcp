from unittest.mock import patch

import bridge_status


def test_generation_script_check_reports_current_script():
    result = bridge_status.check_generation_script()
    assert result.id == "pipeline"
    assert result.ok


def test_gpu_check_handles_missing_nvidia_smi():
    with patch("bridge_status.shutil.which", return_value=None):
        result = bridge_status.check_gpu()
    assert not result.ok
    assert "nvidia-smi" in result.detail


def test_wsl_check_converts_success_to_bridge_result():
    with patch("bridge_status.shutil.which", return_value="wsl.exe"), patch(
        "bridge_status._run", return_value=(True, "연결됨")
    ):
        result = bridge_status.check_wsl()
    assert result.ok
    assert result.detail == "Ubuntu-24.04 연결됨"
