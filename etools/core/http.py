# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
"""HTTP with an explicit User-Agent policy, retry, and an on-disk cache.

The User-Agent is a *policy*, not a detail. Hosts disagree about it in ways
that are invisible until they bite:

* **FRED** silently drops requests carrying an unrecognized User-Agent --
  the connection is accepted, the HTTP/2 stream is reset, and nothing ever
  comes back. A browser-looking UA is dropped too. urllib's own default is
  accepted. So: send no User-Agent header (``OMIT``).
* **SEC EDGAR** requires a descriptive UA naming a contact address, and
  returns 403 without one.

Each source therefore declares its own, rather than the transport guessing.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

#: Send no User-Agent header at all, letting urllib supply its default.
#: Required for FRED. See the module docstring.
OMIT = None

DEFAULT_CACHE = Path(".etools/http-cache")

RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class Response:
    url: str
    status: int
    body: bytes
    from_cache: bool

    def text(self, encoding: str = "utf-8-sig") -> str:
        return self.body.decode(encoding)


class FetchError(RuntimeError):
    """A request failed after exhausting its retries."""


def _cache_path(root: Path, url: str) -> Path:
    return root / (hashlib.sha256(url.encode()).hexdigest()[:32] + ".json")


def get(
    url: str,
    *,
    user_agent: str | None = OMIT,
    timeout: float = 15.0,
    retries: int = 3,
    backoff: float = 1.5,
    cache_dir: Path | str | None = DEFAULT_CACHE,
    cache_ttl: float | None = None,
) -> Response:
    """Fetch ``url``, with retry and an optional on-disk cache.

    ``cache_ttl`` of ``None`` disables caching for this call; a number is a
    maximum age in seconds.
    """
    root = Path(cache_dir) if cache_dir is not None else None
    if root is not None and cache_ttl is not None:
        path = _cache_path(root, url)
        if path.exists() and (time.time() - path.stat().st_mtime) < cache_ttl:
            blob = json.loads(path.read_text())
            return Response(url, blob["status"], bytes.fromhex(blob["body"]), True)

    headers = {} if user_agent is OMIT else {"User-Agent": user_agent}
    last: Exception | None = None

    for attempt in range(retries):
        try:
            with urlopen(Request(url, headers=headers), timeout=timeout) as r:
                resp = Response(url, r.status, r.read(), False)
            break
        except HTTPError as e:
            last = e
            if e.code not in RETRY_STATUS:
                raise FetchError(f"{url}: HTTP {e.code} {e.reason}") from e
        except (URLError, TimeoutError, OSError) as e:
            last = e
        if attempt < retries - 1:
            time.sleep(backoff ** attempt)
    else:
        raise FetchError(f"{url}: giving up after {retries} attempts: {last}") from last

    if root is not None and cache_ttl is not None:
        root.mkdir(parents=True, exist_ok=True)
        _cache_path(root, url).write_text(
            json.dumps({"status": resp.status, "body": resp.body.hex()})
        )
    return resp
