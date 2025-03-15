import sys
import io  # ✅ Import io module
import os
import pytest
import torch
import numpy as np
import json
import hashlib
import time
import gc
import allure
from unittest.mock import patch, MagicMock, mock_open
from concurrent.futures import ThreadPoolExecutor

# ✅ Ensure the project root is in the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# ✅ Import the correct module path
from neurons.Validator.miner_script_m_merkletree import (
    get_gpu_info,
    estimate_vram_size,
    adjust_matrix_size,
    get_seeds,
    get_challenge_indices,
    build_merkle_tree_rows,
    get_merkle_proof_row,
    xorshift32_torch,
    generate_matrix_torch,
    process_gpu,
    run_benchmark,
    benchmark_matrix_multiplication,
    run_compute,
    run_proof_gpu,
    run_proof
)


# --- ✅ Mock Fixtures ---
@pytest.fixture
def mock_cuda_available():
    """Mock CUDA availability."""
    with patch("torch.cuda.is_available", return_value=True):
        yield

@pytest.fixture
def mock_no_cuda():
    """Mock CUDA being unavailable."""
    with patch("torch.cuda.is_available", return_value=False):
        yield

@pytest.fixture
def mock_gpu_count():
    """Mock GPU count."""
    with patch("torch.cuda.device_count", return_value=2):
        yield

@pytest.fixture
def mock_gpu_info():
    """Mock GPU info output."""
    return {
        "num_gpus": 2,
        "gpu_names": ["NVIDIA RTX 3090", "NVIDIA RTX A5000"]
    }

@pytest.fixture
def mock_seeds():
    """Mock seed file content."""
    return "2\n0 12345 67890\n1 54321 98765"

@pytest.fixture
def mock_challenge_indices():
    """Mock challenge indices file content."""
    return "0 10,20;30,40\n1 15,25;35,45"


# --- ✅ Test Classes ---
@allure.feature("GPU Information")
class TestGPUInfo:
    @allure.story("Detect Available GPUs")
    @patch("torch.cuda.is_available", return_value=True)  # ✅ Ensure CUDA is available
    @patch("torch.cuda.device_count", return_value=2)
    @patch("torch.cuda.get_device_name", side_effect=["NVIDIA RTX 3090", "NVIDIA RTX A5000"])
    def test_get_gpu_info(self, mock_cuda_available, mock_device_count, mock_device_name):
        """get_gpu_info: Should correctly list available GPUs and print formatted JSON"""
        expected_output = json.dumps(
            {"num_gpus": 2, "gpu_names": ["NVIDIA RTX 3090", "NVIDIA RTX A5000"]},
            indent=2
        ).strip()

        with allure.step("Fetching GPU details"):
            captured_output = io.StringIO()  # ✅ Capture stdout
            sys.stdout = captured_output  # Redirect stdout

            get_gpu_info()  # ✅ Call function

            sys.stdout = sys.__stdout__  # ✅ Reset stdout

        printed_output = captured_output.getvalue().strip()  # ✅ Get captured output

        with allure.step("Validating GPU information output"):
            assert printed_output == expected_output, f"❌ Expected:\n{expected_output}\n\n✅ Got:\n{printed_output}"

    @allure.story("Handle No GPU Case")
    @patch("torch.cuda.is_available", return_value=False)  # Mock CUDA as unavailable
    def test_get_gpu_info_no_gpu(self, mock_no_cuda):
        """get_gpu_info: Should return zero GPUs if no CUDA is available"""
        with allure.step("Checking system GPU availability"):
            expected_output = {"num_gpus": 0, "gpu_names": []}
            result = get_gpu_info()

        with allure.step("Validating output when no GPU is present"):
            assert result == expected_output, f"Expected {expected_output}, got {result}"


@allure.feature("VRAM Estimation")
class TestVRAMEstimation:
    @allure.story("Estimate VRAM Size for FP16")
    @patch("torch.empty")
    def test_estimate_vram_size_fp16(self, mock_empty):
        """estimate_vram_size: Should return usable VRAM estimate for FP16"""
        with allure.step("Simulating memory allocation failure"):
            mock_empty.side_effect = RuntimeError()

        with allure.step("Running VRAM estimation"):
            vram = estimate_vram_size(precision="fp16")

        with allure.step("Checking estimated VRAM is non-zero"):
            assert vram > 0, f"Expected VRAM > 0, got {vram}"

    @allure.story("Estimate VRAM Size for FP32")
    @patch("torch.empty")
    def test_estimate_vram_size_fp32(self, mock_empty):
        """estimate_vram_size: Should return usable VRAM estimate for FP32"""
        with allure.step("Simulating memory allocation failure"):
            mock_empty.side_effect = RuntimeError()

        with allure.step("Running VRAM estimation"):
            vram = estimate_vram_size(precision="fp32")

        with allure.step("Checking estimated VRAM is non-zero"):
            assert vram > 0, f"Expected VRAM > 0, got {vram}"


@allure.feature("Compute Pipeline")
class TestComputePipeline:
    @allure.story("Handle No GPU Case")
    @patch("torch.cuda.device_count", return_value=0)  # Ensure this returns 0 when CUDA is unavailable
    @patch("torch.cuda.is_available", return_value=False)  # Mock no GPU
    @patch("builtins.print")  # Mock print to catch output
    @patch("os.path.exists", return_value=True)  # Fake that the file exists
    @patch("builtins.open", new_callable=mock_open, read_data="2\n0 12345 67890\n1 54321 98765")  # Fake seed file content
    def test_run_compute(self, mock_open_fn, mock_exists, mock_print, mock_no_cuda, mock_device_count):
        """run_compute: Should handle no GPU case without executing further."""
        with allure.step("Running compute pipeline without GPU"):
            with pytest.raises(SystemExit) as exit_exception:
                run_compute()

        with allure.step("Ensuring error message is printed"):
            mock_print.assert_called_with("Error: No GPU detected.")

        with allure.step("Validating that program exits with error code 1"):
            assert exit_exception.value.code == 1, "Expected exit code 1 when no GPU is detected."


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