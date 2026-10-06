# Orbit OpenSearch: operations and security

This guide organizes runtime behavior documented by the package. It does not certify production readiness. Verify provider/client versions, permissions, transport security, limits, and failure behavior in the target environment before release.

## Configuration surface

Environment names found in the package README:

- `ORBIT_OPENSEARCH_ALLOW_REMOTE_TESTS`
- `ORBIT_OPENSEARCH_CA_CERTS`
- `ORBIT_OPENSEARCH_PASSWORD`
- `ORBIT_OPENSEARCH_URL`
- `ORBIT_OPENSEARCH_USERNAME`

Use the package README's constructor and deployment examples. Store credentials in a secret manager and avoid logging credentials, raw provider errors, request data, or opaque cursors.

## Lifecycle, failure behavior, and limits

`orbit-search-opensearch` is the optional OpenSearch adapter for `orbit-search`. Install the capability
and this provider explicitly:

```bash
python -m pip install 'orbit-search' 'orbit-search-opensearch[opensearch]'
```

```python
from orbit_search_opensearch import OpenSearchStore
from orbit_search import SearchQuery

store = OpenSearchStore.connect(
    ["https://search.example.internal:9200"],
    http_auth=(username, password),  # load both values from a secret manager
    ca_certs="/etc/ssl/certs/search-ca.pem",
    cursor_secret=cursor_secret_from_secret_manager,
)
try:
    page = await store.search("articles", SearchQuery(text="async", fields=("title",)))
finally:
    await store.aclose()
```

The adapter translates portable full-text and exact-match filters into OpenSearch Query DSL. It
uses asynchronous `opensearch-py`, PIT plus `search_after` for a consistent bounded cursor, signs
opaque cursors with the configured shared secret, limits each page to 100 hits, refuses partial/time-out
results, sanitizes provider errors, propagates cancellation, and drains active searches before
closing its owned client. PITs expire after one minute; all workers serving a cursor must share the same high-entropy secret from a secret manager. Do not log cursors because they contain snapshot identifiers.

TLS certificate verification is enabled by default. Supply credentials through a secret manager;
there are no default credentials. For local development, HTTP/TLS overrides must be explicit.
The adapter does not provision indexes, ingest documents, manage mappings, retry searches, or
claim live-cluster compatibility. Validate permissions and the supported server/client versions
in your deployment environment before release.

This package is pre-alpha and supports Python 3.11–3.14. Its opt-in live integration check passed
against OpenSearch 2.19.1 with `opensearch-py` 3.2.0. That local check validates this combination;
it does not establish compatibility with other server/client versions or production topology.
The package suite passes on Python 3.11–3.14; on Python 3.12–3.14 the opt-in live test skips when no
service endpoint is configured.
OpenSearch's official async client guide recommends `opensearch-py[async]` and explicit client
closure; the provider APIs and lifecycle are owned by this package.

## Production validation

Validate startup/shutdown cleanup, timeout and cancellation behavior, concurrency and payload bounds where applicable, secret rotation and least-privilege access, data durability, backup/restore, and failover against the selected provider. Do not infer distributed or durable guarantees from an in-process API or fake-client tests.
