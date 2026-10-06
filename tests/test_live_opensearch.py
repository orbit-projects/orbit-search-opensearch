# Copyright 2026-present Orbit Contributors.
# Licensed under the Apache License, Version 2.0.
"""Opt-in provider checks against a disposable OpenSearch index."""

from __future__ import annotations

import os
from urllib.parse import urlsplit
from uuid import uuid4

import pytest
from orbit_search import SearchQuery

from orbit_search_opensearch import OpenSearchStore


@pytest.mark.asyncio
async def test_live_opensearch_search_and_pit_pagination() -> None:
    """Exercise the official SDK and signed PIT cursor against a real server."""
    endpoint = os.environ.get("ORBIT_OPENSEARCH_URL")
    if not endpoint:
        pytest.skip("Set ORBIT_OPENSEARCH_URL to run the live OpenSearch check.")
    parsed = urlsplit(endpoint)
    local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if not local and os.environ.get("ORBIT_OPENSEARCH_ALLOW_REMOTE_TESTS") != "1":
        pytest.skip("Set ORBIT_OPENSEARCH_ALLOW_REMOTE_TESTS=1 for a remote test service.")

    from opensearchpy import AsyncOpenSearch

    use_ssl = parsed.scheme == "https"
    ca_certs = os.environ.get("ORBIT_OPENSEARCH_CA_CERTS")
    username = os.environ.get("ORBIT_OPENSEARCH_USERNAME")
    password = os.environ.get("ORBIT_OPENSEARCH_PASSWORD")
    http_auth = (username, password) if username is not None and password is not None else None
    setup_options: dict[str, object] = {
        "hosts": [endpoint],
        "use_ssl": use_ssl,
        "verify_certs": use_ssl,
        "request_timeout": 10,
    }
    if ca_certs is not None:
        setup_options["ca_certs"] = ca_certs
    if http_auth is not None:
        setup_options["http_auth"] = http_auth

    index = f"orbit-live-{uuid4().hex}"
    setup_client = AsyncOpenSearch(**setup_options)
    store: OpenSearchStore | None = None
    try:
        await setup_client.indices.create(
            index=index,
            body={
                "mappings": {
                    "properties": {
                        "title": {"type": "text"},
                        "visibility": {"type": "keyword"},
                    }
                }
            },
        )
        await setup_client.index(
            index=index,
            id="public-one",
            body={"title": "async search pagination", "visibility": "public"},
            refresh=True,
        )
        await setup_client.index(
            index=index,
            id="public-two",
            body={"title": "async search adapters", "visibility": "public"},
            refresh=True,
        )
        await setup_client.index(
            index=index,
            id="private",
            body={"title": "async search private", "visibility": "private"},
            refresh=True,
        )

        store = OpenSearchStore.connect(
            endpoint,
            http_auth=http_auth,
            ca_certs=ca_certs,
            use_ssl=use_ssl,
            verify_certs=use_ssl,
            cursor_secret=b"o" * 32,
            request_timeout=5,
        )
        query = SearchQuery(
            text="async search",
            fields=("title",),
            filters={"visibility": "public"},
            page_size=1,
        )
        first = await store.search(index, query)
        assert len(first.hits) == 1
        assert first.next_cursor is not None
        second = await store.search(index, query.model_copy(update={"cursor": first.next_cursor}))
        assert len(second.hits) == 1
        assert second.next_cursor is None
        assert {first.hits[0].id, second.hits[0].id} == {"public-one", "public-two"}
    finally:
        if store is not None:
            await store.aclose()
        await setup_client.indices.delete(index=index, ignore=404)
        await setup_client.close()
