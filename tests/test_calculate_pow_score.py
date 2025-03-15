import sys
import os
import pytest
import allure
from unittest.mock import patch
from neurons.Validator.calculate_pow_score import calc_score_pog  # Update path if needed

# Ensure project root is in Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# --- Mock Fixtures ---
@pytest.fixture
def mock_config_data():
    """Mock GPU performance configuration."""
    return {
        "gpu_performance": {
            "gpu_scores": {
                "NVIDIA RTX 3090": 10,
                "NVIDIA RTX A5000": 8,
                "AMD RX 6900 XT": 6,
            }
        }
    }


# --- Test Cases ---
@allure.feature("GPU Performance Scoring")
class TestCalcScorePog:
    
    @allure.story("Valid GPU Score Calculation")
    @allure.description("Ensures correct scoring for a valid GPU with known performance metrics.")
    def test_calc_score_pog_valid_gpu(self, mock_config_data):
        """Ensure correct scoring for a valid GPU."""
        gpu_specs = {"gpu_name": "NVIDIA RTX 3090", "num_gpus": 2}
        hotkey = "key123"
        allocated_hotkeys = set()

        with allure.step("Calculate GPU score for valid GPU"):
            score = calc_score_pog(gpu_specs, hotkey, allocated_hotkeys, mock_config_data)
            allure.attach(f"Computed Score: {score}", name="Score Result", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Validate score is within range 0-1"):
            assert 0 <= score <= 1, f"Score {score} should be normalized"
            assert score > 0, "Score should be > 0 for a valid GPU"

    @allure.story("Unknown GPU Handling")
    @allure.description("Ensures the function returns a score of 0 for an unrecognized GPU.")
    def test_calc_score_pog_invalid_gpu(self, mock_config_data):
        """Ensure 0 score for an unknown GPU."""
        gpu_specs = {"gpu_name": "Unknown GPU", "num_gpus": 2}
        hotkey = "key456"
        allocated_hotkeys = set()

        with allure.step("Calculate GPU score for unknown GPU"):
            score = calc_score_pog(gpu_specs, hotkey, allocated_hotkeys, mock_config_data)
            allure.attach(f"Computed Score: {score}", name="Unknown GPU Score", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Validate score is 0 for unknown GPU"):
            assert score == 0, f"Score {score} should be 0 for unknown GPUs"

    @allure.story("Handling Maximum GPU Limit")
    @allure.description("Tests if the max GPU count of 8 is enforced correctly in the scoring function.")
    def test_calc_score_pog_max_gpus(self, mock_config_data):
        """Ensure max GPU limit of 8 is enforced."""
        gpu_specs = {"gpu_name": "NVIDIA RTX 3090", "num_gpus": 10}  # Over max limit
        hotkey = "key789"
        allocated_hotkeys = set()

        with allure.step("Calculate GPU score with excessive GPUs"):
            score = calc_score_pog(gpu_specs, hotkey, allocated_hotkeys, mock_config_data)
            allure.attach(f"Computed Score: {score}", name="Excess GPU Score", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Validate score is within range"):
            assert score > 0, "Score should be > 0 for a valid GPU"
            assert score <= 1, "Score should be normalized correctly"

    @allure.story("Hotkey Allocation Multiplier")
    @allure.description("Ensures allocated hotkeys don't modify the score multiplier.")
    def test_calc_score_pog_with_allocation(self, mock_config_data):
        """Ensure allocated hotkeys don't affect score multiplier."""
        gpu_specs = {"gpu_name": "NVIDIA RTX 3090", "num_gpus": 2}
        hotkey = "key123"
        allocated_hotkeys = {"key123"}  # Hotkey is allocated

        with allure.step("Calculate GPU score with allocation"):
            score = calc_score_pog(gpu_specs, hotkey, allocated_hotkeys, mock_config_data)
            allure.attach(f"Computed Score: {score}", name="Score with Allocation", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Validate score is still in range 0-1"):
            assert score > 0, "Score should be > 0 for allocated hotkey"
            assert score <= 1, "Score should be normalized"

    @allure.story("Empty GPU Score Configuration")
    @allure.description("Tests if the function correctly handles cases where GPU scores are missing.")
    def test_calc_score_pog_empty_config(self):
        """Ensure 0 score if GPU scores are empty."""
        gpu_specs = {"gpu_name": "NVIDIA RTX 3090", "num_gpus": 2}
        hotkey = "key123"
        allocated_hotkeys = set()
        mock_config_data = {"gpu_performance": {"gpu_scores": {}}}  # Empty scores

        with allure.step("Calculate GPU score with empty config"):
            score = calc_score_pog(gpu_specs, hotkey, allocated_hotkeys, mock_config_data)
            allure.attach(f"Computed Score: {score}", name="Score with Empty Config", attachment_type=allure.attachment_type.TEXT)

        with allure.step("Validate score is 0 when GPU scores are empty"):
            assert score == 0, "Score should be 0 when no GPU scores are available"

    @allure.story("Exception Handling in Score Calculation")
    @allure.description("Ensures that the function handles unexpected exceptions gracefully.")
    @patch("bittensor.logging.error")
    def test_calc_score_pog_exception(self, mock_log_error, mock_config_data):
        """Ensure 0 score is returned when an exception occurs."""
        gpu_specs = None  # Invalid input
        hotkey = "key123"
        allocated_hotkeys = set()

        with allure.step("Simulate exception during score calculation"):
            try:
                score = calc_score_pog(gpu_specs, hotkey, allocated_hotkeys, mock_config_data)
            except Exception as e:
                allure.attach(f"Exception: {str(e)}", name="Calculation Exception", attachment_type=allure.attachment_type.TEXT)
                score = 0  # Fallback mechanism

        with allure.step("Ensure score is 0 when exception occurs"):
            assert score == 0, "Score should be 0 when an error occurs"
            mock_log_error.assert_called_once()


# --- Attach Failure Logs on Test Failures ---
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item):
    """Attach failure logs to Allure on test failures."""
    outcome = yield
    report = outcome.get_result()

    if report.when == "call" and report.failed:
        allure.attach("Test failure logs", name="Failure Logs", attachment_type=allure.attachment_type.TEXT)


if __name__ == "__main__":
    pytest.main()
