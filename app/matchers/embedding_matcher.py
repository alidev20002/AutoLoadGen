"""Vector embedding matcher for detecting semantic similarity between API fields."""

from __future__ import annotations

import logging
import re
from functools import lru_cache
from urllib.parse import urlsplit
from pathlib import Path
import numpy as np

from sentence_transformers import SentenceTransformer
from huggingface_hub import snapshot_download

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.6
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_DIR = BASE_DIR / "cache" / "all-MiniLM-L6-v2"

REQUIRED_FILES = [
    "model.safetensors",
    "modules.json",
    "config.json",
    "config_sentence_transformers.json",
    "sentence_bert_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "vocab.txt",
    "1_Pooling/config.json",
]

@lru_cache(maxsize=4)
def _load_all_minilm_model():
    missing_files = [
        f for f in REQUIRED_FILES
        if not (MODEL_DIR / f).is_file()
    ]

    if missing_files:
        print("Downloading original model files...")

        snapshot_download(
            repo_id=MODEL_NAME,
            local_dir=str(MODEL_DIR),
            allow_patterns=REQUIRED_FILES,
        )

    print("Loading local model...")

    return SentenceTransformer(
        str(MODEL_DIR.resolve()),
        device="cpu",
        local_files_only=True,
    )

_HTTP_METHOD_RE = re.compile(
    r"^\s*(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\s+",
    flags=re.IGNORECASE,
)
_BOILERPLATE_SEGMENTS = {"api", "rest", "graphql"}
_VERSION_SEGMENT_RE = re.compile(r"^v\d+(?:\.\d+)*$", flags=re.IGNORECASE)
_NUMERIC_ID_RE = re.compile(r"^\d+$")
_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    flags=re.IGNORECASE,
)
_HEX_HASH_RE = re.compile(r"^[0-9a-f]{16,}$", flags=re.IGNORECASE)

def _normalize_field(field_name: str) -> str:
    """Strip synthetic root wrappers and normalize field name."""
    cleaned = field_name.strip()
    cleaned = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", cleaned)
    cleaned = re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", cleaned)
    cleaned = cleaned.lower()
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return " ".join(cleaned.split())


def _is_garbage_segment(segment: str, field_value: str | None = None) -> bool:
    """Return True if a URL path segment is a dynamic value, ID, or API boilerplate."""
    if field_value and segment == field_value:
        return True
    lower = segment.lower()
    if lower in _BOILERPLATE_SEGMENTS or _VERSION_SEGMENT_RE.match(lower):
        return True
    if _NUMERIC_ID_RE.match(segment) or _UUID_RE.match(segment) or _HEX_HASH_RE.match(segment):
        return True
    return False


def _normalize_endpoint(endpoint: str, field_value: str | None = None) -> str:
    """Extract meaningful resource words from an endpoint URL independent of base URL."""
    cleaned = _HTTP_METHOD_RE.sub("", endpoint.strip())

    if "://" in cleaned:
        cleaned = urlsplit(cleaned).path

    cleaned = cleaned.split("?", 1)[0].split("#", 1)[0]
    target_val = str(field_value).strip() if field_value else None

    meaningful_parts = [
        part for part in cleaned.split("/")
        if part and not _is_garbage_segment(part, target_val)
    ]

    # Keep up to the last two meaningful resource segments for concise context.
    selected = meaningful_parts[-2:] if meaningful_parts else []
    return _normalize_field(" ".join(selected))


def _format_field_context(endpoint: str, field_name: str, field_value: str | None = None) -> str:
    """Format cleaned endpoint path and field name into textual prompt for embedding."""
    return (
        f"API endpoint: {_normalize_endpoint(endpoint, field_value)}. "
        f"Field name: {_normalize_field(field_name)}."
    )

def field_match_embedding(
    producer_endpoint: str,
    producer_field: str,
    consumer_endpoint: str,
    consumer_field: str,
    consumer_value: str = "",
    producer_value: str = "",
    model_name: str = DEFAULT_EMBEDDING_MODEL,
) -> tuple[bool | None, float]:
    """Compute semantic similarity score between producer and consumer fields."""

    norm_producer = _normalize_field(producer_field)
    norm_consumer = _normalize_field(consumer_field)

    if not norm_producer or not norm_consumer:
        return False, 0.0

    try:
        model = _load_all_minilm_model()
        texts = [
            _format_field_context(producer_endpoint, producer_field, producer_value),
            _format_field_context(consumer_endpoint, consumer_field, consumer_value),
        ]

        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        context_score = float(np.dot(embeddings[0], embeddings[1]))
        is_match = context_score >= SIMILARITY_THRESHOLD
        return is_match, context_score
    except Exception as exc:
        logger.warning("Embedding comparison failed: %s", exc)
        return None, 0.0
