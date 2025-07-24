TIMEOUT = 10
import os
import re
from urllib.parse import unquote, urlparse

import httpx


def get_remote_filename(response: httpx.Response) -> str | None:
    """
    Extracts the filename from the Content-Disposition header or the URL.

    Args:
        response: The httpx.Response object.

    Returns:
        The extracted filename as a string, or None if not found.
    """
    content_disposition = response.headers.get("Content-Disposition")
    if content_disposition:
        filename_match = re.search(
            r"filename\*=(.+)", content_disposition, re.IGNORECASE
        )
        if filename_match:
            encoded_filename = filename_match.group(1).strip()
            try:
                if "''" in encoded_filename:
                    parts = encoded_filename.split("''", 1)
                    if len(parts) == 2:
                        return unquote(parts[1])
                return unquote(
                    encoded_filename
                )  # Fallback for simple URL-encoded parts
            except Exception:
                pass  # Fallback to filename or URL if decoding fails

        filename_match = re.search(
            r"filename=\"?([^\";]+)\"?", content_disposition, re.IGNORECASE
        )
        if filename_match:
            return unquote(filename_match.group(1).strip())

    parsed_url = urlparse(str(response.url))  # Convert httpx.URL to string for urlparse
    path = parsed_url.path
    if path:
        filename_from_url = os.path.basename(path)
        if filename_from_url:
            filename_from_url = filename_from_url.split("?")[0].split("#")[0]
            return unquote(filename_from_url)  # Unquote URL-encoded characters

    return None
