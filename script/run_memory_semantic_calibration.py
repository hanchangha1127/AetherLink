#!/usr/bin/env python3
"""Review-only semantic duplicate calibration with an optional loopback Ollama run."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import math
import re
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence


MINIMUM_THRESHOLD = 8_000
MAXIMUM_THRESHOLD = 10_000
MAXIMUM_ENTRY_COUNT = 64
MAXIMUM_TEXT_UTF8_BYTES = 262_144
MAXIMUM_EMBEDDING_DIMENSION = 65_536
MAXIMUM_CORPUS_BYTES = 8 * 1_024 * 1_024
MAXIMUM_TAGS_RESPONSE_BYTES = 2 * 1_024 * 1_024
MAXIMUM_SHOW_RESPONSE_BYTES = 2 * 1_024 * 1_024
MAXIMUM_EMBED_RESPONSE_BYTES = 32 * 1_024 * 1_024
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_CORPUS = (
    Path(__file__).resolve().parents[1]
    / "shared/evaluation/memory-semantic-duplicate-calibration-v1.json"
)
LOWERCASE_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class CalibrationError(Exception):
    """A deliberately payload-free calibration failure."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        del message
        raise CalibrationError("arguments_invalid")


@dataclass(frozen=True)
class Entry:
    entry_id: str
    content: str
    offline_embedding: tuple[float, ...]


@dataclass(frozen=True)
class PairLabel:
    first_entry_id: str
    second_entry_id: str
    is_duplicate: bool


@dataclass(frozen=True)
class Corpus:
    corpus_id: str
    review_threshold_basis_points: int
    entries: tuple[Entry, ...]
    pair_labels: tuple[PairLabel, ...]
    expected_review_clusters: tuple[tuple[str, ...], ...]
    sha256: str


@dataclass(frozen=True)
class WorkingCluster:
    indexes: tuple[int, ...]
    minimum_score: int


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise CalibrationError("duplicate_json_key")
        result[key] = value
    return result


def _reject_nonfinite_constant(_: str) -> None:
    raise CalibrationError("invalid_json_number")


def strict_json_loads(raw: bytes, error_code: str) -> Any:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise CalibrationError(error_code) from None
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_keys,
            parse_constant=_reject_nonfinite_constant,
        )
    except CalibrationError:
        raise
    except (json.JSONDecodeError, ValueError, RecursionError):
        raise CalibrationError(error_code) from None


def _exact_object(value: Any, code: str) -> dict[str, Any]:
    if type(value) is not dict:
        raise CalibrationError(code)
    return value


def _exact_array(value: Any, code: str) -> list[Any]:
    if type(value) is not list:
        raise CalibrationError(code)
    return value


def _exact_string(value: Any, code: str, *, nonempty: bool = True) -> str:
    if type(value) is not str or (nonempty and not value):
        raise CalibrationError(code)
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise CalibrationError(code) from None
    return value


def _exact_int(value: Any, code: str) -> int:
    if type(value) is not int:
        raise CalibrationError(code)
    return value


def _exact_bool(value: Any, code: str) -> bool:
    if type(value) is not bool:
        raise CalibrationError(code)
    return value


def _finite_number(value: Any, code: str) -> float:
    if type(value) not in (int, float):
        raise CalibrationError(code)
    try:
        converted = float(value)
    except (OverflowError, ValueError):
        raise CalibrationError(code) from None
    if not math.isfinite(converted):
        raise CalibrationError(code)
    return converted


def _require_exact_keys(value: dict[str, Any], keys: set[str], code: str) -> None:
    if set(value) != keys:
        raise CalibrationError(code)


def _utf8_key(value: str) -> bytes:
    return value.encode("utf-8")


def _cluster_key(entry_ids: Sequence[str]) -> tuple[bytes, ...]:
    return tuple(_utf8_key(entry_id) for entry_id in entry_ids)


def load_corpus(path: Path) -> Corpus:
    try:
        raw = path.read_bytes()
    except OSError:
        raise CalibrationError("corpus_unreadable") from None
    if not raw or len(raw) > MAXIMUM_CORPUS_BYTES:
        raise CalibrationError("corpus_size_invalid")

    root = _exact_object(strict_json_loads(raw, "corpus_json_invalid"), "corpus_invalid")
    _require_exact_keys(
        root,
        {
            "schema_version",
            "corpus_id",
            "review_threshold_basis_points",
            "entries",
            "pair_labels",
            "expected_review_clusters",
        },
        "corpus_keys_invalid",
    )
    if _exact_int(root["schema_version"], "schema_version_invalid") != 1:
        raise CalibrationError("schema_version_invalid")
    corpus_id = _exact_string(root["corpus_id"], "corpus_id_invalid")
    if len(corpus_id.encode("utf-8")) > 256:
        raise CalibrationError("corpus_id_invalid")
    review_threshold = _exact_int(
        root["review_threshold_basis_points"], "review_threshold_invalid"
    )
    if not MINIMUM_THRESHOLD <= review_threshold <= MAXIMUM_THRESHOLD:
        raise CalibrationError("review_threshold_invalid")

    raw_entries = _exact_array(root["entries"], "entries_invalid")
    if not 2 <= len(raw_entries) <= MAXIMUM_ENTRY_COUNT:
        raise CalibrationError("entry_count_invalid")
    entries: list[Entry] = []
    seen_ids: set[str] = set()
    total_text_bytes = 0
    embedding_dimension: int | None = None
    for raw_entry in raw_entries:
        entry_object = _exact_object(raw_entry, "entry_invalid")
        _require_exact_keys(
            entry_object,
            {"id", "language", "content", "offline_embedding"},
            "entry_keys_invalid",
        )
        entry_id = _exact_string(entry_object["id"], "entry_id_invalid")
        if len(entry_id.encode("utf-8")) > 256 or entry_id in seen_ids:
            raise CalibrationError("entry_id_invalid")
        seen_ids.add(entry_id)
        language = _exact_string(entry_object["language"], "language_invalid")
        if len(language.encode("utf-8")) > 64:
            raise CalibrationError("language_invalid")
        content = _exact_string(entry_object["content"], "content_invalid")
        if not content.strip():
            raise CalibrationError("content_invalid")
        content_size = len(content.encode("utf-8"))
        total_text_bytes += content_size
        if content_size > MAXIMUM_TEXT_UTF8_BYTES or total_text_bytes > MAXIMUM_TEXT_UTF8_BYTES:
            raise CalibrationError("content_size_invalid")
        raw_embedding = _exact_array(
            entry_object["offline_embedding"], "offline_embedding_invalid"
        )
        if not raw_embedding or len(raw_embedding) > MAXIMUM_EMBEDDING_DIMENSION:
            raise CalibrationError("offline_embedding_dimension_invalid")
        if embedding_dimension is None:
            embedding_dimension = len(raw_embedding)
        elif len(raw_embedding) != embedding_dimension:
            raise CalibrationError("offline_embedding_dimension_invalid")
        embedding = tuple(
            _finite_number(value, "offline_embedding_invalid") for value in raw_embedding
        )
        entries.append(Entry(entry_id, content, embedding))

    raw_labels = _exact_array(root["pair_labels"], "pair_labels_invalid")
    maximum_pair_count = len(entries) * (len(entries) - 1) // 2
    if not raw_labels or len(raw_labels) > maximum_pair_count:
        raise CalibrationError("pair_label_count_invalid")
    pair_labels: list[PairLabel] = []
    seen_pairs: set[tuple[str, str]] = set()
    positive_count = 0
    negative_count = 0
    for raw_label in raw_labels:
        label_object = _exact_object(raw_label, "pair_label_invalid")
        _require_exact_keys(
            label_object,
            {"first_entry_id", "second_entry_id", "is_duplicate"},
            "pair_label_keys_invalid",
        )
        first = _exact_string(label_object["first_entry_id"], "pair_entry_id_invalid")
        second = _exact_string(label_object["second_entry_id"], "pair_entry_id_invalid")
        if first not in seen_ids or second not in seen_ids:
            raise CalibrationError("pair_entry_id_invalid")
        if _utf8_key(first) >= _utf8_key(second):
            raise CalibrationError("pair_order_invalid")
        pair = (first, second)
        if pair in seen_pairs:
            raise CalibrationError("pair_duplicate")
        seen_pairs.add(pair)
        is_duplicate = _exact_bool(label_object["is_duplicate"], "pair_label_type_invalid")
        positive_count += int(is_duplicate)
        negative_count += int(not is_duplicate)
        pair_labels.append(PairLabel(first, second, is_duplicate))
    if positive_count == 0 or negative_count == 0:
        raise CalibrationError("pair_label_class_invalid")

    raw_clusters = _exact_array(
        root["expected_review_clusters"], "expected_clusters_invalid"
    )
    if len(raw_clusters) > 100:
        raise CalibrationError("expected_clusters_invalid")
    expected_clusters: list[tuple[str, ...]] = []
    clustered_ids: set[str] = set()
    for raw_cluster in raw_clusters:
        cluster_values = _exact_array(raw_cluster, "expected_cluster_invalid")
        if not 2 <= len(cluster_values) <= len(entries):
            raise CalibrationError("expected_cluster_invalid")
        cluster = tuple(
            _exact_string(value, "expected_cluster_entry_invalid") for value in cluster_values
        )
        if any(entry_id not in seen_ids for entry_id in cluster):
            raise CalibrationError("expected_cluster_entry_invalid")
        if tuple(sorted(cluster, key=_utf8_key)) != cluster:
            raise CalibrationError("expected_cluster_order_invalid")
        if any(entry_id in clustered_ids for entry_id in cluster):
            raise CalibrationError("expected_cluster_duplicate_entry")
        clustered_ids.update(cluster)
        expected_clusters.append(cluster)
    if tuple(sorted(expected_clusters, key=_cluster_key)) != tuple(expected_clusters):
        raise CalibrationError("expected_clusters_order_invalid")

    return Corpus(
        corpus_id=corpus_id,
        review_threshold_basis_points=review_threshold,
        entries=tuple(entries),
        pair_labels=tuple(pair_labels),
        expected_review_clusters=tuple(expected_clusters),
        sha256=hashlib.sha256(raw).hexdigest(),
    )


def normalize_embeddings(embeddings: Sequence[Sequence[float]]) -> list[list[float]]:
    if not embeddings:
        raise CalibrationError("embedding_count_invalid")
    dimension = len(embeddings[0])
    if not 1 <= dimension <= MAXIMUM_EMBEDDING_DIMENSION:
        raise CalibrationError("embedding_dimension_invalid")
    normalized: list[list[float]] = []
    for embedding in embeddings:
        if len(embedding) != dimension:
            raise CalibrationError("embedding_dimension_invalid")
        values = [_finite_number(value, "embedding_value_invalid") for value in embedding]
        scale = max(abs(value) for value in values)
        if not math.isfinite(scale) or scale <= 0:
            raise CalibrationError("embedding_value_invalid")
        scaled = [value / scale for value in values]
        magnitude = math.sqrt(sum(value * value for value in scaled))
        if not math.isfinite(magnitude) or magnitude <= 0:
            raise CalibrationError("embedding_value_invalid")
        normalized.append([value / magnitude for value in scaled])
    return normalized


def round_nearest_away_from_zero(value: float) -> int:
    if value >= 0:
        return math.floor(value + 0.5)
    return math.ceil(value - 0.5)


def similarity_basis_points(lhs: Sequence[float], rhs: Sequence[float]) -> int:
    cosine = sum(left * right for left, right in zip(lhs, rhs))
    bounded = min(1.0, max(-1.0, cosine))
    return round_nearest_away_from_zero(bounded * MAXIMUM_THRESHOLD)


def _ratio_basis_points(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return (numerator * MAXIMUM_THRESHOLD + denominator // 2) // denominator


def _metrics(pair_scores: Sequence[dict[str, Any]], threshold: int) -> dict[str, Any]:
    true_positive = false_positive = true_negative = false_negative = 0
    for pair in pair_scores:
        predicted = pair["is_semantic_candidate"] and pair["similarity_basis_points"] >= threshold
        actual = pair["is_duplicate"]
        if actual and predicted:
            true_positive += 1
        elif not actual and predicted:
            false_positive += 1
        elif not actual and not predicted:
            true_negative += 1
        else:
            false_negative += 1
    predicted_positive = true_positive + false_positive
    actual_positive = true_positive + false_negative
    return {
        "threshold_basis_points": threshold,
        "true_positive_count": true_positive,
        "false_positive_count": false_positive,
        "true_negative_count": true_negative,
        "false_negative_count": false_negative,
        "precision_basis_points": (
            None
            if predicted_positive == 0
            else _ratio_basis_points(true_positive, predicted_positive)
        ),
        "recall_basis_points": _ratio_basis_points(true_positive, actual_positive),
        "f1_basis_points": _ratio_basis_points(
            2 * true_positive,
            2 * true_positive + false_positive + false_negative,
        ),
    }


def _complete_link_clusters(
    corpus: Corpus,
    normalized: Sequence[Sequence[float]],
) -> list[dict[str, Any]]:
    indexes = sorted(range(len(corpus.entries)), key=lambda index: _utf8_key(corpus.entries[index].entry_id))
    scores: list[list[int | None]] = [
        [None for _ in corpus.entries] for _ in corpus.entries
    ]
    threshold = corpus.review_threshold_basis_points
    for first_offset, first_index in enumerate(indexes[:-1]):
        for second_index in indexes[first_offset + 1 :]:
            first = corpus.entries[first_index]
            second = corpus.entries[second_index]
            if first.content.encode("utf-8") == second.content.encode("utf-8"):
                continue
            score = similarity_basis_points(normalized[first_index], normalized[second_index])
            if score >= threshold:
                scores[first_index][second_index] = score
                scores[second_index][first_index] = score

    def ids_for(cluster: WorkingCluster) -> tuple[str, ...]:
        return tuple(corpus.entries[index].entry_id for index in cluster.indexes)

    working = [WorkingCluster((index,), MAXIMUM_THRESHOLD) for index in indexes]
    while len(working) >= 2:
        best: tuple[int, tuple[bytes, ...], int, int, tuple[int, ...]] | None = None
        for first_working in range(len(working) - 1):
            for second_working in range(first_working + 1, len(working)):
                lhs = working[first_working]
                rhs = working[second_working]
                cross_scores: list[int] = []
                eligible = True
                for lhs_index in lhs.indexes:
                    for rhs_index in rhs.indexes:
                        score = scores[lhs_index][rhs_index]
                        if score is None:
                            eligible = False
                            break
                        cross_scores.append(score)
                    if not eligible:
                        break
                if not eligible:
                    continue
                minimum_score = min(lhs.minimum_score, rhs.minimum_score, *cross_scores)
                merged_indexes = tuple(
                    sorted(
                        lhs.indexes + rhs.indexes,
                        key=lambda index: _utf8_key(corpus.entries[index].entry_id),
                    )
                )
                merged_ids = tuple(corpus.entries[index].entry_id for index in merged_indexes)
                candidate = (
                    -minimum_score,
                    _cluster_key(merged_ids),
                    first_working,
                    second_working,
                    merged_indexes,
                )
                if best is None or candidate[:2] < best[:2]:
                    best = candidate
        if best is None:
            break
        negative_score, _, first_working, second_working, merged_indexes = best
        del working[second_working]
        del working[first_working]
        working.append(WorkingCluster(merged_indexes, -negative_score))
        working.sort(key=lambda cluster: _cluster_key(ids_for(cluster)))

    result = [
        {
            "entry_ids": list(ids_for(cluster)),
            "minimum_similarity_basis_points": cluster.minimum_score,
        }
        for cluster in working
        if len(cluster.indexes) >= 2
    ]
    result.sort(
        key=lambda cluster: (
            -cluster["minimum_similarity_basis_points"],
            _cluster_key(cluster["entry_ids"]),
        )
    )
    return result


def evaluate(corpus: Corpus, embeddings: Sequence[Sequence[float]], mode: str) -> dict[str, Any]:
    if len(embeddings) != len(corpus.entries):
        raise CalibrationError("embedding_count_invalid")
    normalized = normalize_embeddings(embeddings)
    indexes = {entry.entry_id: index for index, entry in enumerate(corpus.entries)}
    pair_scores: list[dict[str, Any]] = []
    for label in corpus.pair_labels:
        first_index = indexes[label.first_entry_id]
        second_index = indexes[label.second_entry_id]
        pair_scores.append(
            {
                "first_entry_id": label.first_entry_id,
                "second_entry_id": label.second_entry_id,
                "is_duplicate": label.is_duplicate,
                "is_semantic_candidate": (
                    corpus.entries[first_index].content.encode("utf-8")
                    != corpus.entries[second_index].content.encode("utf-8")
                ),
                "similarity_basis_points": similarity_basis_points(
                    normalized[first_index], normalized[second_index]
                ),
            }
        )
    pair_scores.sort(
        key=lambda pair: (
            _utf8_key(pair["first_entry_id"]),
            _utf8_key(pair["second_entry_id"]),
        )
    )

    all_metrics = [
        _metrics(pair_scores, threshold)
        for threshold in range(MINIMUM_THRESHOLD, MAXIMUM_THRESHOLD + 1)
    ]
    best_metrics = max(
        all_metrics,
        key=lambda metrics: (
            metrics["f1_basis_points"],
            -1 if metrics["precision_basis_points"] is None else metrics["precision_basis_points"],
            metrics["threshold_basis_points"],
        ),
    )
    review_metrics = all_metrics[corpus.review_threshold_basis_points - MINIMUM_THRESHOLD]
    predicted_clusters = _complete_link_clusters(corpus, normalized)
    predicted_ids = sorted(
        (tuple(cluster["entry_ids"]) for cluster in predicted_clusters),
        key=_cluster_key,
    )

    return {
        "schema_version": 1,
        "corpus_id": corpus.corpus_id,
        "corpus_sha256": corpus.sha256,
        "mode": mode,
        "aggregate_metrics": {
            "sweep_minimum_threshold_basis_points": MINIMUM_THRESHOLD,
            "sweep_maximum_threshold_basis_points": MAXIMUM_THRESHOLD,
            "sweep_step_basis_points": 1,
            "sweep_threshold_count": len(all_metrics),
            "best_f1": best_metrics,
            "review_threshold": review_metrics,
        },
        "pair_scores": pair_scores,
        "predicted_review_clusters": predicted_clusters,
        "review_clusters_exact_match": tuple(predicted_ids) == corpus.expected_review_clusters,
        "default_threshold_changed": False,
        "automatic_memory_mutation": False,
        "protocol_changed": False,
    }


def _read_bounded_response(response: http.client.HTTPResponse, maximum_bytes: int) -> bytes:
    length_header = response.getheader("Content-Length")
    if length_header is not None:
        try:
            declared_length = int(length_header, 10)
        except ValueError:
            raise CalibrationError("provider_response_invalid") from None
        if declared_length < 0 or declared_length > maximum_bytes:
            raise CalibrationError("provider_response_too_large")
    try:
        data = response.read(maximum_bytes + 1)
    except (OSError, http.client.HTTPException):
        raise CalibrationError("provider_transport_failed") from None
    if len(data) > maximum_bytes:
        raise CalibrationError("provider_response_too_large")
    return data


def _remaining_timeout_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise CalibrationError("provider_deadline_exceeded")
    return remaining


def _request_json(
    connection: http.client.HTTPConnection,
    method: str,
    path: str,
    maximum_response_bytes: int,
    deadline: float,
    body: bytes | None = None,
) -> Any:
    headers = {"Accept": "application/json", "Connection": "close"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Content-Length"] = str(len(body))
    response_holder: list[http.client.HTTPResponse] = []
    deadline_expired = threading.Event()

    def expire_request() -> None:
        deadline_expired.set()
        if response_holder:
            try:
                response_holder[0].close()
            except (OSError, http.client.HTTPException):
                pass
        try:
            connection.close()
        except (OSError, http.client.HTTPException):
            pass

    timer = threading.Timer(_remaining_timeout_seconds(deadline), expire_request)
    timer.daemon = True
    timer.start()
    try:
        try:
            connection.request(method, path, body=body, headers=headers)
            response = connection.getresponse()
            response_holder.append(response)
            raw = _read_bounded_response(response, maximum_response_bytes)
        except CalibrationError as error:
            if error.code == "provider_transport_failed" and (
                deadline_expired.is_set() or time.monotonic() >= deadline
            ):
                raise CalibrationError("provider_deadline_exceeded") from None
            raise
        except (OSError, http.client.HTTPException):
            if deadline_expired.is_set() or time.monotonic() >= deadline:
                raise CalibrationError("provider_deadline_exceeded") from None
            raise CalibrationError("provider_transport_failed") from None
        if deadline_expired.is_set() or time.monotonic() >= deadline:
            raise CalibrationError("provider_deadline_exceeded")
        if response.status != 200:
            raise CalibrationError("provider_http_status_invalid")
        parsed = strict_json_loads(raw, "provider_json_invalid")
        if deadline_expired.is_set() or time.monotonic() >= deadline:
            raise CalibrationError("provider_deadline_exceeded")
        return parsed
    finally:
        timer.cancel()


def _validate_capabilities(value: Any) -> None:
    capabilities = _exact_array(value, "provider_capabilities_invalid")
    seen: set[str] = set()
    for item in capabilities:
        capability = _exact_string(item, "provider_capabilities_invalid")
        if capability in seen:
            raise CalibrationError("provider_capabilities_invalid")
        seen.add(capability)
    if "embedding" not in seen:
        raise CalibrationError("provider_embedding_capability_missing")


def _exact_model_from_tags(
    tags: dict[str, Any],
    model: str,
) -> tuple[dict[str, Any], str]:
    raw_models = _exact_array(tags.get("models"), "provider_tags_invalid")
    matches: list[dict[str, Any]] = []
    for raw_model in raw_models:
        model_object = _exact_object(raw_model, "provider_tags_invalid")
        name_value = model_object.get("name", model_object.get("model"))
        name = _exact_string(name_value, "provider_model_name_invalid")
        if "name" in model_object and "model" in model_object:
            if _exact_string(model_object["model"], "provider_model_name_invalid") != name:
                raise CalibrationError("provider_model_name_invalid")
        if name == model:
            matches.append(model_object)
    if len(matches) != 1:
        raise CalibrationError("provider_exact_model_missing")
    matched = matches[0]
    digest = _exact_string(matched.get("digest"), "provider_model_digest_invalid")
    if LOWERCASE_SHA256_RE.fullmatch(digest) is None:
        raise CalibrationError("provider_model_digest_invalid")
    return matched, digest


def fetch_live_embeddings(
    corpus: Corpus,
    host: str,
    port: int,
    model: str,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    connection_factory: Callable[..., http.client.HTTPConnection] = http.client.HTTPConnection,
) -> tuple[list[list[float]], str]:
    if host != "127.0.0.1":
        raise CalibrationError("host_not_loopback_literal")
    if type(port) is not int or not 1 <= port <= 65_535:
        raise CalibrationError("port_invalid")
    if type(timeout_seconds) not in (int, float) or isinstance(timeout_seconds, bool):
        raise CalibrationError("timeout_invalid")
    if not math.isfinite(float(timeout_seconds)) or not 0 < timeout_seconds <= 60:
        raise CalibrationError("timeout_invalid")
    model = _exact_string(model, "model_invalid")
    if (
        len(model.encode("utf-8")) > 256
        or model.strip() != model
        or any(character.isspace() or ord(character) < 0x21 for character in model)
    ):
        raise CalibrationError("model_invalid")

    deadline = time.monotonic() + float(timeout_seconds)

    def connection() -> http.client.HTTPConnection:
        return connection_factory(host, port, timeout=_remaining_timeout_seconds(deadline))

    tags_connection = connection()
    try:
        tags = _exact_object(
            _request_json(
                tags_connection,
                "GET",
                "/api/tags",
                MAXIMUM_TAGS_RESPONSE_BYTES,
                deadline,
            ),
            "provider_tags_invalid",
        )
    finally:
        tags_connection.close()
    matched, digest = _exact_model_from_tags(tags, model)

    if "capabilities" in matched:
        _validate_capabilities(matched["capabilities"])
    else:
        show_body = json.dumps(
            {"model": model}, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")
        show_connection = connection()
        try:
            show = _exact_object(
                _request_json(
                    show_connection,
                    "POST",
                    "/api/show",
                    MAXIMUM_SHOW_RESPONSE_BYTES,
                    deadline,
                    show_body,
                ),
                "provider_show_invalid",
            )
        finally:
            show_connection.close()
        _validate_capabilities(show.get("capabilities"))

    texts = [entry.content for entry in corpus.entries]
    text_bytes = sum(len(value.encode("utf-8")) for value in texts)
    if not texts or len(texts) > MAXIMUM_ENTRY_COUNT or text_bytes > MAXIMUM_TEXT_UTF8_BYTES:
        raise CalibrationError("embed_request_size_invalid")
    embed_body = json.dumps(
        {"model": model, "input": texts, "truncate": False},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    embed_connection = connection()
    try:
        embed_response = _exact_object(
            _request_json(
                embed_connection,
                "POST",
                "/api/embed",
                MAXIMUM_EMBED_RESPONSE_BYTES,
                deadline,
                embed_body,
            ),
            "provider_embed_invalid",
        )
    finally:
        embed_connection.close()
    raw_embeddings = _exact_array(
        embed_response.get("embeddings"), "provider_embeddings_invalid"
    )
    if len(raw_embeddings) != len(corpus.entries):
        raise CalibrationError("embedding_count_invalid")
    embeddings: list[list[float]] = []
    dimension: int | None = None
    for raw_embedding in raw_embeddings:
        values = _exact_array(raw_embedding, "embedding_dimension_invalid")
        if not values or len(values) > MAXIMUM_EMBEDDING_DIMENSION:
            raise CalibrationError("embedding_dimension_invalid")
        if dimension is None:
            dimension = len(values)
        elif len(values) != dimension:
            raise CalibrationError("embedding_dimension_invalid")
        embeddings.append([_finite_number(value, "embedding_value_invalid") for value in values])
    normalize_embeddings(embeddings)

    final_tags_connection = connection()
    try:
        final_tags = _exact_object(
            _request_json(
                final_tags_connection,
                "GET",
                "/api/tags",
                MAXIMUM_TAGS_RESPONSE_BYTES,
                deadline,
            ),
            "provider_tags_invalid",
        )
    finally:
        final_tags_connection.close()
    final_matched, final_digest = _exact_model_from_tags(final_tags, model)
    if final_digest != digest:
        raise CalibrationError("provider_model_changed_during_run")
    if "capabilities" in final_matched:
        _validate_capabilities(final_matched["capabilities"])
    return embeddings, f"ollama-sha256:{digest}"


def build_parser() -> argparse.ArgumentParser:
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--mode", choices=("offline", "live-ollama"), default="offline")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--model")
    parser.add_argument("--timeout-seconds", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def run(args: argparse.Namespace) -> dict[str, Any]:
    corpus = load_corpus(args.corpus)
    if args.mode == "offline":
        if args.host is not None or args.port is not None or args.model is not None:
            raise CalibrationError("live_arguments_forbidden_offline")
        return evaluate(corpus, [entry.offline_embedding for entry in corpus.entries], "offline")
    if args.host is None or args.port is None or args.model is None:
        raise CalibrationError("live_arguments_required")
    embeddings, fingerprint = fetch_live_embeddings(
        corpus,
        args.host,
        args.port,
        args.model,
        args.timeout_seconds,
    )
    report = evaluate(corpus, embeddings, "live-ollama")
    report["model_id"] = f"ollama:{args.model}"
    report["model_fingerprint"] = fingerprint
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
        report = run(args)
    except CalibrationError as error:
        print(f"calibration_error:{error.code}", file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
