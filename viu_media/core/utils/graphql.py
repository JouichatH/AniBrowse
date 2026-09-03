import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from httpx import Client, Response

from .networking import TIMEOUT

if TYPE_CHECKING:
    from httpx import Client

logger = logging.getLogger(__name__)


def load_graphql_from_file(file: Path) -> str:
    """
    Reads and returns the content of a .gql file.

    Args:
        file: The Path object pointing to the .gql file.

    Returns:
        The string content of the file.
    """
    try:
        return file.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error(f"GraphQL file not found at: {file}")
        raise


def execute_graphql_query_with_get_request(
    url: str, httpx_client: Client, graphql_file: Path, variables: dict
) -> Response:
    query = load_graphql_from_file(graphql_file)
    params = {"query": query, "variables": json.dumps(variables)}
    response = httpx_client.get(url, params=params, timeout=TIMEOUT)
    return response


def execute_graphql(
    url: str, httpx_client: Client, graphql_file: Path, variables: dict, headers: dict | None = None
) -> Response:
    query = load_graphql_from_file(graphql_file)
    json_body = {"query": query, "variables": variables}
    response = httpx_client.post(url, json=json_body, headers=headers, timeout=TIMEOUT)
    return response


def graphql_error_message(response: Response) -> str | None:
    """The server's own explanation when a GraphQL response carries no data.

    A GraphQL endpoint answers a refusal with a 4xx/5xx *and* an ``errors``
    array while omitting ``data`` entirely - AniList did exactly this when it
    disabled its API ("temporarily disabled due to severe stability issues"),
    and mappers that reach straight into ``data["data"]`` turned that into an
    unreadable ``'NoneType' object is not subscriptable``. Returns None when the
    response is usable, so callers can treat a message as "give up and say why".
    """
    try:
        payload = response.json()
    except Exception:  # noqa: BLE001 - a non-JSON body is itself a failure
        if response.is_success:
            return None
        return f"HTTP {response.status_code} from {response.url.host}"

    if isinstance(payload, dict) and payload.get("data") is not None:
        return None  # usable, even if partial errors rode along

    messages = []
    if isinstance(payload, dict):
        for err in payload.get("errors") or []:
            if isinstance(err, dict) and err.get("message"):
                messages.append(str(err["message"]))
    if messages:
        return "; ".join(dict.fromkeys(messages))
    if not response.is_success:
        return f"HTTP {response.status_code} from {response.url.host}"
    return "the API returned no data"
