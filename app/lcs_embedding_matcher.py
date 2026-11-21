"""Hybrid LCS-Embedding matcher for detecting API field dependencies."""

from __future__ import annotations

from collections.abc import Callable

from . import embedding_matcher as _EMBEDDING


def field_match_lcs_embedding(
    producer_endpoint: str,
    producer_field: str,
    consumer_endpoint: str,
    consumer_field: str,
    lcs_match_fn: Callable[[], bool],
    consumer_value: str = "",
    producer_value: str = "",
    model_name: str = _EMBEDDING.DEFAULT_EMBEDDING_MODEL,
) -> tuple[bool | None, float]:
    """Evaluate dependency using LCS first, then Embedding if LCS does not match.

    1. Run ``lcs_match_fn()``. If True, immediately return ``(True, 1.0)``.
    2. Otherwise, run ``embedding_matcher.field_match_embedding`` and return its result.
    """
    if lcs_match_fn():
        return True, 1.0

    return _EMBEDDING.field_match_embedding(
        producer_endpoint=producer_endpoint,
        producer_field=producer_field,
        consumer_endpoint=consumer_endpoint,
        consumer_field=consumer_field,
        consumer_value=consumer_value,
        producer_value=producer_value,
        model_name=model_name,
    )
