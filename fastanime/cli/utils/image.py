# fastanime/cli/utils/image.py

from __future__ import annotations

import logging
import shutil
import subprocess
from typing import Optional

import click
import httpx

logger = logging.getLogger(__name__)


def render_image(url: str, capture: bool = False, size: str = "30x30") -> Optional[str]:
    """
    Renders an image from a URL in the terminal using icat or chafa.

    This function automatically detects the best available tool.

    Args:
        url: The URL of the image to render.
        capture: If True, returns the terminal-formatted image as a string
                 instead of printing it. Defaults to False.
        size: The size parameter to pass to the rendering tool (e.g., "WxH").

    Returns:
        If capture is True, returns the image data as a string.
        If capture is False, prints directly to the terminal and returns None.
        Returns None on any failure.
    """
    # --- Common subprocess arguments ---
    subprocess_kwargs = {
        "check": False,  # We will handle errors manually
        "capture_output": capture,
        "text": capture,  # Decode stdout/stderr as text if capturing
    }

    # --- Try icat (Kitty terminal) first ---
    if icat_executable := shutil.which("icat"):
        process = subprocess.run(
            [icat_executable, "--align", "left", url], **subprocess_kwargs
        )
        if process.returncode == 0:
            return process.stdout if capture else None
        logger.warning(f"icat failed for URL {url} with code {process.returncode}")

    # --- Fallback to chafa ---
    if chafa_executable := shutil.which("chafa"):
        try:
            # Chafa requires downloading the image data first
            with httpx.Client() as client:
                response = client.get(url, follow_redirects=True, timeout=20)
                response.raise_for_status()
                img_bytes = response.content

            # Add stdin input to the subprocess arguments
            subprocess_kwargs["input"] = img_bytes

            process = subprocess.run(
                [chafa_executable, f"--size={size}", "-"], **subprocess_kwargs
            )
            if process.returncode == 0:
                return process.stdout if capture else None
            logger.warning(f"chafa failed for URL {url} with code {process.returncode}")

        except httpx.HTTPStatusError as e:
            logger.error(
                f"HTTP error fetching image for chafa: {e.response.status_code}"
            )
            click.echo(
                f"[dim]Error fetching image: {e.response.status_code}[/dim]", err=True
            )
        except Exception as e:
            logger.error(f"An exception occurred while running chafa: {e}")

        return None

    # --- Final fallback if no tool is found ---
    if not capture:
        # Only show this message if the user expected to see something.
        click.echo(
            "[dim](Image preview skipped: icat or chafa not found)[/dim]", err=True
        )

    return None
