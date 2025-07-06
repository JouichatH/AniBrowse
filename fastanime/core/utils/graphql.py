import json
from pathlib import Path

from httpx import AsyncClient, Client, Response
from typing_extensions import Counter

from .networking import TIMEOUT


def execute_graphql_query(
    url: str, httpx_client: Client, graphql_file: Path, variables: dict
):
    response = httpx_client.get(
        url,
        params={
            "variables": json.dumps(variables),
            "query": load_graphql_from_file(graphql_file),
        },
        timeout=TIMEOUT,
    )
    return response


def load_graphql_from_file(file: Path) -> str:
    query = file.read_text(encoding="utf-8")
    return query
