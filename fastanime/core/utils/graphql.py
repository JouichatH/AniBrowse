from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

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


def execute_graphql_query(
    url: str, httpx_client: Client, graphql_file: Path, variables: dict
) -> dict | None:
    """
    Executes a GraphQL query using a GET request with query parameters.
    Suitable for read-only operations.

    Args:
        url: The base GraphQL endpoint URL.
        httpx_client: The httpx.Client instance to use.
        graphql_file: Path to the .gql file containing the query.
        variables: A dictionary of variables for the query.

    Returns:
        The JSON response as a dictionary, or None on failure.
    """
    query = load_graphql_from_file(graphql_file)
    params = {"query": query, "variables": json.dumps(variables)}
    try:
        response = httpx_client.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"GraphQL GET request failed for {graphql_file.name}: {e}")
        return None


def execute_graphql_mutation(
    url: str, httpx_client: Client, graphql_file: Path, variables: dict
) -> dict | None:
    """
    Executes a GraphQL mutation using a POST request with a JSON body.
    Suitable for write/update operations.

    Args:
        url: The GraphQL endpoint URL.
        httpx_client: The httpx.Client instance to use.
        graphql_file: Path to the .gql file containing the mutation.
        variables: A dictionary of variables for the mutation.

    Returns:
        The JSON response as a dictionary, or None on failure.
    """
    query = load_graphql_from_file(graphql_file)
    json_body = {"query": query, "variables": variables}
    try:
        response = httpx_client.post(url, json=json_body, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logger.error(f"GraphQL POST request failed for {graphql_file.name}: {e}")
        return None
