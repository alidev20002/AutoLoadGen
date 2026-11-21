"""LCS-Embedding Hybrid Matcher Approach for API Dependency Detection.

Implements a two-stage hybrid dependency detection pipeline:
1. First evaluate the match request using the LCS matcher.
2. If LCS detects a match, immediately return True.
3. Otherwise, evaluate the match request using the Embedding matcher and return its result.

All LCS and Embedding models, thresholds, and configurations mirror their
respective standalone matchers (LCS_matcher_approach and Embedding_matcher_approach).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Callable

import numpy as np

# Ensure project modules are importable
_CURRENT_DIR = Path(__file__).resolve().parent
_SEARCH_PATHS = [
    _CURRENT_DIR,
    _CURRENT_DIR.parent,
]
for p in _SEARCH_PATHS:
    if p.is_dir() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from Embedding_matcher_approach import (
    EmbeddingMatcher,
    SECONDARY_EMBEDDING_MODEL,
    SIMILARITY_THRESHOLD,
    VALIDATOR_SCORE_THRESHOLD,
    match_fields as embedding_match_fields,
)
from LCS_matcher_approach import (
    LCS_THRESHOLD,
    LCSMatcher,
    match_fields as lcs_match_fields,
)

logger = logging.getLogger(__name__)


def match_fields(
    producer_endpoint: str,
    producer_field: str,
    producer_value: Any,
    consumer_endpoint: str,
    consumer_field: str,
    consumer_value: Any,
    location: str = "body",
    producer_method: str = "",
    consumer_method: str = "",
    father_name: str | None = None,
    xpath: str | None = None,
    model_name: str = SECONDARY_EMBEDDING_MODEL,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
    validator_threshold: float = VALIDATOR_SCORE_THRESHOLD,
    fallback_to_lcs: bool = False,
    lcs_threshold: float = LCS_THRESHOLD,
    encoder_fn: Callable[[list[str]], np.ndarray] | None = None,
) -> bool:
    """Evaluate API dependency using the LCS-Embedding hybrid pipeline.

    1. Process the request with LCS matching. If LCS detects a match, return True.
    2. Otherwise, process the request with Embedding matching and return its result.
    """
    if lcs_match_fields(
        producer_endpoint=producer_endpoint,
        producer_field=producer_field,
        producer_value=producer_value,
        consumer_endpoint=consumer_endpoint,
        consumer_field=consumer_field,
        consumer_value=consumer_value,
        location=location,
        producer_method=producer_method,
        consumer_method=consumer_method,
        father_name=father_name,
        threshold=lcs_threshold,
    ):
        return True

    return embedding_match_fields(
        producer_endpoint=producer_endpoint,
        producer_field=producer_field,
        producer_value=producer_value,
        consumer_endpoint=consumer_endpoint,
        consumer_field=consumer_field,
        consumer_value=consumer_value,
        location=location,
        producer_method=producer_method,
        consumer_method=consumer_method,
        father_name=father_name,
        xpath=xpath,
        model_name=model_name,
        similarity_threshold=similarity_threshold,
        validator_threshold=validator_threshold,
        fallback_to_lcs=fallback_to_lcs,
        lcs_threshold=lcs_threshold,
        encoder_fn=encoder_fn,
    )


class LCSEmbeddingMatcher:
    """LCS-Embedding Hybrid Dependency Matcher class for running benchmark testcases."""

    def __init__(
        self,
        model_name: str = SECONDARY_EMBEDDING_MODEL,
        similarity_threshold: float = SIMILARITY_THRESHOLD,
        validator_threshold: float = VALIDATOR_SCORE_THRESHOLD,
        fallback_to_lcs: bool = False,
        lcs_threshold: float = LCS_THRESHOLD,
        encoder_fn: Callable[[list[str]], np.ndarray] | None = None,
    ):
        self.model_name = model_name
        self.similarity_threshold = similarity_threshold
        self.validator_threshold = validator_threshold
        self.fallback_to_lcs = fallback_to_lcs
        self.lcs_threshold = lcs_threshold
        self.encoder_fn = encoder_fn
        self.lcs_matcher = LCSMatcher(threshold=lcs_threshold)
        self.embedding_matcher = EmbeddingMatcher(
            model_name=model_name,
            similarity_threshold=similarity_threshold,
            validator_threshold=validator_threshold,
            fallback_to_lcs=fallback_to_lcs,
            lcs_threshold=lcs_threshold,
            encoder_fn=encoder_fn,
        )
        self.name = "LCS-Embedding"

    def match(self, testcase: dict[str, Any]) -> bool:
        """Run LCS-Embedding hybrid approach on a benchmark testcase dictionary."""
        if self.lcs_matcher.match(testcase):
            return True
        return self.embedding_matcher.match(testcase)

    def predict(self, testcase: dict[str, Any]) -> bool:
        """Alias for match()."""
        return self.match(testcase)


# Convenience module-level functions
_DEFAULT_MATCHER = LCSEmbeddingMatcher()


def match(testcase: dict[str, Any]) -> bool:
    """Evaluate a testcase using the LCS-Embedding hybrid approach."""
    return _DEFAULT_MATCHER.match(testcase)


def predict(testcase: dict[str, Any]) -> bool:
    """Evaluate a testcase using the LCS-Embedding hybrid approach."""
    return _DEFAULT_MATCHER.predict(testcase)


def evaluate_testcase(testcase: dict[str, Any]) -> bool:
    """Alias for match()."""
    return _DEFAULT_MATCHER.match(testcase)
