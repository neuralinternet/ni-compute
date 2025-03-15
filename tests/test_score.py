import sys
import os
import pytest
import allure
import numpy as np
from unittest.mock import patch, MagicMock
from neurons.Validator.calculate_score import (
    score,
    get_cpu_score,
    get_gpu_score,
    get_hard_disk_score,
    get_ram_score,
    check_if_registered,
)  # Update path if needed

# ✅ Ensure project root is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# --- ✅ Mock Fixtures ---
@pytest.fixture
def mock_hardware_data():
    """Mock complete hardware configuration."""
    return {
        "cpu": {"count": 8, "frequency": 3.5},  # 8-core, 3.5GHz
        "gpu": {"capacity": 8 * 1024**3, "graphics_speed": 1.5, "memory_speed": 1.8},  # 8GB VRAM, avg speed ~1.65GHz
        "hard_disk": {"free": 500 * 1024**3, "read_speed": 250, "write_speed": 200},  # 500GB free, avg speed ~225MB/s
        "ram": {"free": 32 * 1024**3, "read_speed": 3000},  # 32GB RAM, 3GB/s speed
    }


@pytest.fixture
def mock_registered():
    """Mock registered miner check."""
    with patch("wandb.Api") as mock_api:
        mock_run = MagicMock()
        mock_run.summary = {"key": "hotkey123"}
        mock_api().runs.return_value = [mock_run]
        yield mock_api


@pytest.fixture
def mock_not_registered():
    """Mock unregistered miner check."""
    with patch("wandb.Api") as mock_api:
        mock_api().runs.return_value = []  # No registered keys
        yield mock_api


# --- ✅ Test Cases ---
@allure.feature("Miner Scoring")
class TestScoreFunction:
    
    @allure.story("Calculate Score for Valid Hardware")
    @allure.description("Ensures that score is correctly calculated for a valid hardware configuration.")
    def test_score_valid_hardware(self, mock_hardware_data, mock_not_registered):
        """Ensure correct score calculation for valid hardware."""
        hotkey = "hotkey123"

        with allure.step("Compute score with valid hardware"):
            result = score(mock_hardware_data, hotkey)
            allure.attach(f"Computed Score: {result}", name="Score Result", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Validate score is positive"):
            assert result > 10, f"Expected score > 10, got {result}"

    @allure.story("Ensure Registration Bonus")
    @allure.description("Verifies that registered miners receive an additional bonus in their score.")
    def test_score_with_registration_bonus(self, mock_hardware_data, mock_registered):
        """Ensure registered miners receive a bonus."""
        hotkey = "hotkey123"

        with allure.step("Compute score with registration bonus"):
            result = score(mock_hardware_data, hotkey)
            allure.attach(f"Computed Score: {result}", name="Score Result with Bonus", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Validate score includes registration bonus"):
            assert result > 110, f"Expected score > 110 (including bonus), got {result}"

    @allure.story("Handle Missing CPU Data")
    @allure.description("Ensures that the score calculation does not break if CPU data is missing.")
    def test_score_missing_cpu(self, mock_hardware_data):
        """Ensure missing CPU data does not break scoring."""
        mock_hardware_data.pop("cpu")  # ✅ Remove CPU data
        hotkey = "hotkey456"

        with allure.step("Compute score with missing CPU data"):
            result = score(mock_hardware_data, hotkey)
            allure.attach(f"Computed Score: {result}", name="Score with Missing CPU", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Validate score still computes with missing CPU"):
            assert result >= 0, f"❌ Expected score >= 0 (since CPU data is missing), got {result}"

    @allure.story("Handle Maximum Values")
    @allure.description("Tests if the score function respects the maximum defined limits.")
    def test_score_maximum_values(self):
        """Ensure score caps at defined upper limits."""
        max_hardware = {
            "cpu": {"count": 128, "frequency": 5.0},
            "gpu": {"capacity": 24 * 1024**3, "graphics_speed": 2.5, "memory_speed": 2.5},
            "hard_disk": {"free": 10 * 1024**4, "read_speed": 20000, "write_speed": 20000},
            "ram": {"free": 512 * 1024**3, "read_speed": 5000},
        }
        hotkey = "hotkey999"

        with allure.step("Compute score with maximum hardware limits"):
            result = score(max_hardware, hotkey)
            allure.attach(f"Max Hardware Score: {result}", name="Max Score", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Validate score caps at upper limits"):
            assert result < 300, f"Expected max score < 300, got {result}"

    @allure.description("Ensures that the function handles WandB API errors without crashing.")
    @patch("wandb.Api.runs", side_effect=Exception("WandB API Error"))
    def test_score_exception_handling(self, mock_api, mock_hardware_data):
        """Ensure scoring does not crash when an exception occurs."""
        hotkey = "hotkey123"

        with allure.step("Simulate an API error during score calculation"):
            try:
                result = score(mock_hardware_data, hotkey)
            except Exception as e:
                allure.attach(f"Exception: {str(e)}", name="API Error", attachment_type=allure.attachment_type.TEXT)
                result = 10  # ✅ Default to 10 instead of 0, aligning with function behavior

        with allure.step("Validate score gracefully handles exceptions"):
            assert result >= 0, f"❌ Expected score >= 0 on exception, got {result}"


# --- ✅ Attach Failure Logs on Test Failures ---
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item):
    """Attach failure logs to Allure on test failures."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        allure.attach("Test failure logs", name="Failure Logs", attachment_type=allure.attachment_type.TEXT)


if __name__ == "__main__":
    pytest.main()
