"""Screenshot utilities for capturing HarmonyOS device screen."""

import base64
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from io import BytesIO
from typing import Tuple

from PIL import Image
from phone_agent.hdc.connection import _run_hdc_command
from phone_agent.config.timing import TIMING_CONFIG


@dataclass
class Screenshot:
    """Represents a captured screenshot."""

    base64_data: str
    width: int
    height: int
    is_sensitive: bool = False


def get_screenshot(
    device_id: str | None = None,
    timeout: int | None = None,
    retry_count: int | None = None,
) -> Screenshot:
    """
    Capture a screenshot from the connected HarmonyOS device.

    Args:
        device_id: Optional HDC device ID for multi-device setups.
        timeout: Timeout in seconds for screenshot operations.
                 If None, uses config default (30s).
        retry_count: Number of retry attempts. If None, uses config default (3).

    Returns:
        Screenshot object containing base64 data and dimensions.

    Note:
        If the screenshot fails (e.g., on sensitive screens like payment pages),
        a black fallback image is returned with is_sensitive=True.
        The function will retry on timeout with exponential backoff.
    """
    # Use config defaults if not specified
    if timeout is None:
        timeout = int(TIMING_CONFIG.screenshot.timeout)
    if retry_count is None:
        retry_count = TIMING_CONFIG.screenshot.retry_count

    hdc_prefix = _get_hdc_prefix(device_id)

    # Retry loop
    for attempt in range(retry_count):
        temp_path = os.path.join(tempfile.gettempdir(), f"screenshot_{uuid.uuid4()}.png")
        
        try:
            # Execute screenshot command
            # HarmonyOS HDC only supports JPEG format
            remote_path = "/data/local/tmp/tmp_screenshot.jpeg"

            # Try method 1: hdc shell screenshot (newer HarmonyOS versions)
            result = _run_hdc_command(
                hdc_prefix + ["shell", "screenshot", remote_path],
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            # Check for screenshot failure (sensitive screen)
            output = result.stdout + result.stderr
            if "fail" in output.lower() or "error" in output.lower() or "not found" in output.lower():
                # Try method 2: snapshot_display (older versions or different devices)
                result = _run_hdc_command(
                    hdc_prefix + ["shell", "snapshot_display", "-f", remote_path],
                    capture_output=True,
                    text=True,
                    timeout=timeout,
                )
                output = result.stdout + result.stderr
                if "fail" in output.lower() or "error" in output.lower():
                    print(f"Screenshot blocked (sensitive screen detected)")
                    return _create_fallback_screenshot(is_sensitive=True)

            # Pull screenshot to local temp path
            # Note: remote file is JPEG, but PIL can open it regardless of local extension
            pull_timeout = int(TIMING_CONFIG.screenshot.pull_timeout)
            _run_hdc_command(
                hdc_prefix + ["file", "recv", remote_path, temp_path],
                capture_output=True,
                text=True,
                timeout=pull_timeout,
            )

            if not os.path.exists(temp_path):
                raise FileNotFoundError(f"Screenshot file not found at {temp_path}")

            # Read JPEG image and convert to PNG for model inference
            # PIL automatically detects the image format from file content
            img = Image.open(temp_path)
            width, height = img.size

            buffered = BytesIO()
            img.save(buffered, format="PNG")
            base64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

            # Cleanup
            os.remove(temp_path)

            return Screenshot(
                base64_data=base64_data, width=width, height=height, is_sensitive=False
            )

        except subprocess.TimeoutExpired as e:
            # Handle timeout specifically
            print(f"Screenshot timeout on attempt {attempt + 1}/{retry_count}: {e}")
            
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            
            # If not last attempt, wait before retrying
            if attempt < retry_count - 1:
                retry_delay = TIMING_CONFIG.screenshot.retry_delay
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                # Last attempt failed
                print(f"Screenshot failed after {retry_count} attempts due to timeout")
                return _create_fallback_screenshot(is_sensitive=False)
        
        except Exception as e:
            # Handle other errors
            print(f"Screenshot error on attempt {attempt + 1}/{retry_count}: {e}")
            
            # Clean up temp file if it exists
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass
            
            # If not last attempt, wait before retrying
            if attempt < retry_count - 1:
                retry_delay = TIMING_CONFIG.screenshot.retry_delay
                print(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                # Last attempt failed
                print(f"Screenshot failed after {retry_count} attempts: {e}")
                return _create_fallback_screenshot(is_sensitive=False)
    
    # Should not reach here, but return fallback just in case
    return _create_fallback_screenshot(is_sensitive=False)


def _get_hdc_prefix(device_id: str | None) -> list:
    """Get HDC command prefix with optional device specifier."""
    if device_id:
        return ["hdc", "-t", device_id]
    return ["hdc"]


def _create_fallback_screenshot(is_sensitive: bool) -> Screenshot:
    """Create a black fallback image when screenshot fails."""
    default_width, default_height = 1080, 2400

    black_img = Image.new("RGB", (default_width, default_height), color="black")
    buffered = BytesIO()
    black_img.save(buffered, format="PNG")
    base64_data = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return Screenshot(
        base64_data=base64_data,
        width=default_width,
        height=default_height,
        is_sensitive=is_sensitive,
    )
