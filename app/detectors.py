"""Dependency detectors for identifying correlations across URLs, headers, query parameters, cookies, and payloads."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from . import schema_client
from . import validator as V
from .graph import DependencyGraph, MyNode, make_edge
from .har_model import Cookie
from .response_model import AtomicObject, ResponseUnstructured, StructuredObject

BLACKLIST_HEADERS = {
    # Browser identification
    "user-agent",
    "accept-language",

    # Network / HTTP infrastructure
    "accept-encoding",
    "connection",
    "keep-alive",
    "host",
    "content-length",
    "transfer-encoding",
    "te",
    "trailer",

    # Browser caching
    "cache-control",
    "pragma",

    # Monitoring and distributed tracing
    "baggage",
    "sentry-trace",
    "traceparent",
    "tracestate",

    # Request tracking
    "x-request-id",
    "x-correlation-id",

    # Infrastructure
    "via",
    "x-real-ip",

    # Browser security and metadata
    "upgrade-insecure-requests",
    "dnt",
    "sec-gpc",

    # Browser optimization
    "x-web-optimize-response",

    "x-site",
    "x-source",
    "referer",
    "priority",
    ":path",
    ":scheme",
    ":method",
    "accept",
    "content-type",
    "x-web-client",
    "x-web-client-id",
    ":authority",
    "origin",
    "x-client",
    "x-creation-tags",
    "x-client-info"
}

BLACKLIST_HEADER_PREFIXES = {
    # Browser client hints
    "sec-ch-",

    # Browser fetch metadata
    "sec-fetch-",

    # Infrastructure / reverse proxy
    "x-forwarded-",
}


def _get_node_children(resp: Any) -> list[Any]:
    if isinstance(resp, (ResponseUnstructured, StructuredObject)):
        return resp.objects
    return []


def _walk_atomic(resp: Any, callback: Callable[[AtomicObject, StructuredObject | None], bool]) -> bool:
    """Depth-first search over response structure, stopping early if callback returns True."""
    def _recurse(node: Any, parent_structured: StructuredObject | None) -> bool:
        for item in _get_node_children(node):
            if isinstance(item, AtomicObject):
                if callback(item, parent_structured):
                    return True
            elif isinstance(item, StructuredObject):
                if _recurse(item, item):
                    return True
        return False

    return _recurse(resp, resp if isinstance(resp, StructuredObject) else None)


def check_url(
    responses: list[Any],
    req_idx: int,
    graph: DependencyGraph,
    to_node: MyNode,
    first: int,
) -> None:
    """Detect correlations inside URL path segments."""
    path_segments = urlparse(to_node.request.url).path.split("/")
    for i in range(1, len(path_segments)):
        segment, possible_name = path_segments[i], path_segments[i - 1]
        if not segment:
            continue

        for ri in range(req_idx - 1, first - 1, -1):
            source_node = graph.get_node_by_index(ri)
            if source_node is None:
                continue

            def evaluate_match(atomic: AtomicObject, parent: StructuredObject | None) -> bool:
                if segment == atomic.value and V.evaluate_url_atomic_dep(
                    atomic,
                    source_node.request.url,
                    parent,
                    possible_name,
                    consumer_url=to_node.request.url,
                    producer_method=source_node.request.method,
                    consumer_method=to_node.request.method,
                ):
                    graph.edges.append(
                        make_edge("url", source_node, to_node, atomic, ri, req_idx, subPath=segment)
                    )
                    return True
                return False

            if _walk_atomic(responses[ri], evaluate_match):
                break


def check_header(
    responses: list[Any],
    req_idx: int,
    graph: DependencyGraph,
    to_node: MyNode,
    first: int,
) -> None:
    """Detect correlations inside HTTP request headers."""
    for header in to_node.request.headers:
        if not header.value:
            continue

        header_name_lower = (header.name or "").lower()
        if (
            header_name_lower in BLACKLIST_HEADERS
            or header_name_lower == "cookie"
            or header_name_lower == "set-cookie"
            or any(
                header_name_lower.startswith(prefix)
                for prefix in BLACKLIST_HEADER_PREFIXES
            )
        ):
            continue

        for ri in range(req_idx - 1, first - 1, -1):
            source_node = graph.get_node_by_index(ri)
            if source_node is None:
                continue

            def evaluate_match(atomic: AtomicObject, parent: StructuredObject | None) -> bool:
                if V.evaluate_header_atomic_dep(
                    atomic,
                    header.name,
                    header.value,
                    parent,
                    source_node.request.url,
                    consumer_url=to_node.request.url,
                    producer_method=source_node.request.method,
                    consumer_method=to_node.request.method,
                ):
                    graph.edges.append(
                        make_edge("header", source_node, to_node, atomic, ri, req_idx, header_name=header.name)
                    )
                    return True
                return False

            if _walk_atomic(responses[ri], evaluate_match):
                break


def check_query(
    responses: list[Any],
    req_idx: int,
    graph: DependencyGraph,
    to_node: MyNode,
    first: int,
) -> None:
    """Detect correlations inside URL query parameters."""
    for qparam in to_node.request.queryParams:
        if not qparam.value:
            continue

        for ri in range(req_idx - 1, first - 1, -1):
            source_node = graph.get_node_by_index(ri)
            if source_node is None:
                continue

            def evaluate_match(atomic: AtomicObject, parent: StructuredObject | None) -> bool:
                if V.general_atomic_comparison(
                    atomic,
                    qparam.value,
                    qparam.name,
                    parent,
                    source_node.request.url,
                    consumer_url=to_node.request.url,
                    location="queryparam",
                    producer_method=source_node.request.method,
                    consumer_method=to_node.request.method,
                ):
                    graph.edges.append(
                        make_edge("queryparam", source_node, to_node, atomic, ri, req_idx, query_param_name=qparam.name)
                    )
                    return True
                return False

            if _walk_atomic(responses[ri], evaluate_match):
                break


def check_cookie(
    responses: list[Any],
    req_idx: int,
    graph: DependencyGraph,
    to_node: MyNode,
    first: int,
) -> None:
    """Detect correlations inside request cookies."""
    combined_cookies = list(to_node.request.cookies)
    seen_pairs = {(c.name, c.value) for c in combined_cookies}

    for header in to_node.request.headers:
        if (header.name or "").lower() != "cookie":
            continue
        for pair in (header.value or "").split(";"):
            pair = pair.strip()
            if not pair:
                continue
            name, _, val = pair.partition("=")
            name, val = name.strip(), val.strip()
            if not name:
                continue
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
                val = val[1:-1]
            if (name, val) not in seen_pairs:
                seen_pairs.add((name, val))
                combined_cookies.append(Cookie(name=name, value=val))

    for cookie in combined_cookies:
        if not cookie.value:
            continue

        for ri in range(req_idx - 1, first - 1, -1):
            source_node = graph.get_node_by_index(ri)
            if source_node is None:
                continue

            def evaluate_match(atomic: AtomicObject, parent: StructuredObject | None) -> bool:
                if V.evaluate_cookie_atomic_dep(
                    atomic,
                    cookie.name,
                    cookie.value,
                    parent,
                    source_node.request.url,
                    consumer_url=to_node.request.url,
                    producer_method=source_node.request.method,
                    consumer_method=to_node.request.method,
                ):
                    graph.edges.append(
                        make_edge("cookie", source_node, to_node, atomic, ri, req_idx, name=cookie.name)
                    )
                    return True
                return False

            if _walk_atomic(responses[ri], evaluate_match):
                break


def _schema_match(request_obj_str: str, resp_node: Any) -> StructuredObject | None:
    """Find a non-empty StructuredObject in response node whose JSON schema matches request schema."""
    target_schema = schema_client.generate_json_schema(request_obj_str)
    stack = [resp_node]
    while stack:
        current = stack.pop()
        for child in _get_node_children(current):
            if isinstance(child, StructuredObject):
                if child.schema_string == target_schema and child.objects and child.value not in ("{}", "[]", ""):
                    return child
                stack.append(child)
    return None


def check_body(
    responses: list[Any],
    req_idx: int,
    graph: DependencyGraph,
    to_node: MyNode,
    first: int,
) -> None:
    """Detect correlations in form-urlencoded or JSON request bodies."""
    post_data = to_node.request.postData
    if post_data is None:
        return

    if post_data.mimeType == "application/x-www-form-urlencoded":
        for param in post_data.params:
            if not param.value:
                continue

            for ri in range(req_idx - 1, first - 1, -1):
                source_node = graph.get_node_by_index(ri)
                if source_node is None:
                    continue

                def evaluate_match(atomic: AtomicObject, parent: StructuredObject | None) -> bool:
                    if V.general_atomic_comparison(
                        atomic,
                        param.value,
                        param.name,
                        parent,
                        source_node.request.url,
                        consumer_url=to_node.request.url,
                        location="body",
                        producer_method=source_node.request.method,
                        consumer_method=to_node.request.method,
                    ):
                        graph.edges.append(
                            make_edge("bodyue", source_node, to_node, atomic, ri, req_idx, name=param.name)
                        )
                        return True
                    return False

                if _walk_atomic(responses[ri], evaluate_match):
                    break

    elif post_data.mimeType == "application/json":
        text = (post_data.text or "").strip()
        if not text:
            return
        try:
            body = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            return
        _check_json_value(responses, body, None, req_idx, graph, to_node, first)


def _check_json_value(
    responses: list[Any],
    obj: Any,
    name: str | None,
    req_idx: int,
    graph: DependencyGraph,
    to_node: MyNode,
    first: int,
) -> None:
    """Recursively search for matching JSON structures or primitives within JSON payload."""
    if isinstance(obj, dict):
        if not obj:
            return
        serialized = json.dumps(obj, separators=(",", ":"))
        if _search_schema(responses, serialized, req_idx, graph, to_node, name, first):
            return
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                _check_json_value(responses, v, k, req_idx, graph, to_node, first)
            elif v is not None:
                _check_primitive(responses, str(v), k, req_idx, graph, to_node, first)

    elif isinstance(obj, list):
        if not obj:
            return
        serialized = json.dumps(obj, separators=(",", ":"))
        if _search_schema(responses, serialized, req_idx, graph, to_node, name, first):
            return
        for item in obj:
            if isinstance(item, (dict, list)):
                _check_json_value(responses, item, name, req_idx, graph, to_node, first)
            elif item is not None:
                _check_primitive(responses, str(item), name or "", req_idx, graph, to_node, first)

    elif isinstance(obj, str):
        _check_primitive(responses, obj, name or "", req_idx, graph, to_node, first)


def _search_schema(
    responses: list[Any],
    obj_str: str,
    req_idx: int,
    graph: DependencyGraph,
    to_node: MyNode,
    name: str | None,
    first: int,
) -> bool:
    """Search previous responses for whole-object schema matches, prioritizing most recent."""
    for ri in range(req_idx - 1, first - 1, -1):
        source_node = graph.get_node_by_index(ri)
        if source_node is None:
            continue
        matched_structured = _schema_match(obj_str, responses[ri])
        if matched_structured is not None:
            edge = make_edge(
                "bodyjson",
                source_node,
                to_node,
                None,
                ri,
                req_idx,
                name=name if name else "All",
                primitive=False,
                structured=matched_structured,
            )
            if matched_structured.name == "All":
                edge.name = "All"
            graph.edges.append(edge)
            return True
    return False


def _check_primitive(
    responses: list[Any],
    value: str,
    name: str,
    req_idx: int,
    graph: DependencyGraph,
    to_node: MyNode,
    first: int,
) -> None:
    """Check primitive atomic field match across previous responses, stopping at most recent match."""
    if not value:
        return

    for ri in range(req_idx - 1, first - 1, -1):
        source_node = graph.get_node_by_index(ri)
        if source_node is None:
            continue

        def evaluate_match(atomic: AtomicObject, parent: StructuredObject | None) -> bool:
            if V.general_atomic_comparison(
                atomic,
                value,
                name,
                parent,
                source_node.request.url,
                consumer_url=to_node.request.url,
                location="body",
                producer_method=source_node.request.method,
                consumer_method=to_node.request.method,
            ):
                graph.edges.append(
                    make_edge("bodyjson", source_node, to_node, atomic, ri, req_idx, name=name, primitive=True)
                )
                return True
            return False

        if _walk_atomic(responses[ri], evaluate_match):
            break