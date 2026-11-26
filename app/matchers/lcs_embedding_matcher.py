"""Hybrid LCS-Embedding matcher for detecting API field dependencies."""

from __future__ import annotations

from collections.abc import Callable

from . import embedding_matcher as _EMBEDDING

LCS_ONLY_VALUES = frozenset({"0", "1", "true", "false"})


def _is_lcs_only_value(producer_value: str, consumer_value: str) -> bool:
    return (
        str(consumer_value).strip().lower() in LCS_ONLY_VALUES
        or str(producer_value).strip().lower() in LCS_ONLY_VALUES
    )


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
    2. If the candidate value is one of ``0``, ``1``, ``true``, or ``false``
       (case-insensitive), return ``(False, 0.0)`` without calling Embedding.
    3. Otherwise, run ``embedding_matcher.field_match_embedding`` and return its result.
    """
    if lcs_match_fn():
        return True, 1.0

    if _is_lcs_only_value(producer_value, consumer_value):
        return False, 0.0

    return _EMBEDDING.field_match_embedding(
        producer_endpoint=producer_endpoint,
        producer_field=producer_field,
        consumer_endpoint=consumer_endpoint,
        consumer_field=consumer_field,
        consumer_value=consumer_value,
        producer_value=producer_value,
        model_name=model_name,
    )
