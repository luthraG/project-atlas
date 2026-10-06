"""Conditional GET helpers: weak ETag + Cache-Control, 304 on match."""

import hashlib
import json
from collections.abc import Sequence

from fastapi import Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

CACHE_CONTROL = "private, max-age=60"


def _weak_etag(body: bytes) -> str:
    return f'W/"{hashlib.sha256(body).hexdigest()[:32]}"'


def _matches(if_none_match: str | None, etag: str) -> bool:
    if not if_none_match:
        return False
    candidates = {tag.strip() for tag in if_none_match.split(",")}
    # Weak comparison: W/"x" and "x" are equivalent for If-None-Match.
    opaque = etag.removeprefix("W/")
    return "*" in candidates or etag in candidates or opaque in candidates


def conditional_json(request: Request, items: Sequence[BaseModel], headers: dict) -> Response:
    """200 JSON with validators, or an empty 304 when the client copy is fresh."""
    body = json.dumps(jsonable_encoder(items), separators=(",", ":")).encode()
    etag = _weak_etag(body)
    all_headers = {**headers, "ETag": etag, "Cache-Control": CACHE_CONTROL}
    if _matches(request.headers.get("if-none-match"), etag):
        return Response(status_code=304, headers=all_headers)
    return Response(body, media_type="application/json", headers=all_headers)
