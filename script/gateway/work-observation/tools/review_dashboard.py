#!/usr/bin/env python3
"""Standalone human-review dashboard for offline Guard/Auto replay results.

The analysis index is opened read-only.  Human judgements are stored in a
separate small SQLite database so a reviewer can annotate results without
changing the collector's evidence or competing with the rolling worker.

The server deliberately binds to loopback by default.  It is an operator UI,
not a public API and must not be put in front of the 4000/4001 or 4004/4005
gateway entries.  The latter remain the Tokyo/US gray test lanes; this page
only reads their offline analysis results and stores human labels separately.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
import stat
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlsplit

import rolling
import semantic


MAX_REQUEST_BYTES = 32 * 1024
MAX_PAGE_SIZE = 100
MAX_TEXT = 12_000
MAX_MESSAGES = 40
VALID_GUARD_LABELS = {
    "correct_allow",
    "correct_block",
    "should_allow",
    "should_block",
    "uncertain",
}
VALID_AUTO_LABELS = {
    "good_choice",
    "wrong_model",
    "too_strong",
    "too_weak",
    "uncertain",
}
VALID_REVIEW_STATUS = {"needs_review", "reviewed", "skipped"}
VALID_HUMAN_STATUS_FILTERS = {"needs_review", "reviewed", "skipped", "all"}
EVENT_ID = re.compile(r"^[^/\\]{1,512}$")
DEFAULT_GRAY_LANES = {"tokyo": "4004", "us": "4005"}
DEFAULT_FORMAL_LANES = {"tokyo": "4000", "us": "4001"}
VALID_REVIEW_VIEWS = {"review", "auto", "technical", "backlog", "diagnostic", "all"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _json(value):
    try:
        return json.loads(value) if isinstance(value, str) and value else value
    except (TypeError, ValueError):
        return value


def _truncate(value, limit=MAX_TEXT):
    if not isinstance(value, str):
        return value
    if len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _safe_json(value):
    """Return JSON-compatible data while bounding values shown in the UI."""
    if isinstance(value, str):
        return _truncate(value)
    if isinstance(value, list):
        return [_safe_json(item) for item in value[:MAX_MESSAGES]]
    if isinstance(value, dict):
        return {str(key): _safe_json(item) for key, item in list(value.items())[:100]}
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _message_view(event):
    """Build bounded conversation messages from the immutable source event."""
    messages = semantic._event_messages(event)
    result = []
    for message in messages[:MAX_MESSAGES]:
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "unknown")[:32]
        content = _truncate(message.get("content"), MAX_TEXT)
        if not isinstance(content, str):
            content = json.dumps(_safe_json(content), ensure_ascii=False)
        result.append({"role": role, "content": content})
    return result


def _task_preview(messages):
    for message in messages:
        if message.get("role") == "user" and message.get("content"):
            return _truncate(message["content"], 280)
    return _truncate(messages[0]["content"], 280) if messages else "（没有可展示的任务正文）"


def _job_state(row):
    """Return the queue state even when no semantic result exists yet."""
    return row["job_state"] or row["review_state"] or "unreviewed"


def _guard_display(row):
    """Give the UI a truthful Guard label for every queue state."""
    decision = row["guard_decision"]
    if decision in {"allow", "block", "unavailable"}:
        return {"allow": "放行", "block": "拦截", "unavailable": "Guard 不可用"}[decision]
    state = row["guard_state"]
    if state == "unavailable":
        return "Guard 不可用"
    if state == "http_error":
        return "Guard 请求失败"
    if state == "invalid":
        return "Guard 无有效结论"
    if state == "not_run":
        return "Guard 未运行"
    if not state and _job_state(row) in {"pending", "running"}:
        return "待分析"
    return "Guard 未运行"


def _auto_display(row):
    """Explain why a model name is absent instead of collapsing it to NULL."""
    model = row["auto_model"]
    if isinstance(model, str) and model:
        return model
    state = row["auto_state"]
    if state == "blocked":
        return "Auto 被拒绝（无模型）"
    if state == "unavailable":
        return "Auto 不可用"
    if state == "http_error":
        return "Auto 请求失败"
    if state == "invalid":
        return "Auto 未返回模型"
    if state == "not_run":
        if row["guard_decision"] == "block":
            return "离线未运行（Guard 拦截）"
        return "离线未运行（Guard 无结论）"
    if not state and _job_state(row) in {"pending", "running"}:
        return "待分析"
    if row["guard_decision"] == "block":
        return "线上未运行（Guard 拦截）"
    if row["guard_decision"] in {None, "unavailable"}:
        return "线上未运行（Guard 无结论）"
    return "Auto 未运行"


def _auto_offline_status(row):
    """Classify the result of the isolated offline Auto call."""
    state = row["auto_state"] or ""
    model = row["auto_model"]
    if state == "complete" and isinstance(model, str) and model:
        return "selected"
    if state == "blocked":
        return "blocked"
    if state in {"unavailable", "http_error", "invalid"}:
        return "technical_failure"
    return "not_run"


def _auto_online_status(row):
    """Explain what the production Guard -> Auto path would have done.

    The worker skips Auto when Guard blocks or has no conclusion, so an
    offline model result is never presented as if production Auto executed.
    """
    decision = row["guard_decision"]
    if decision == "block":
        return "not_run_guard_block"
    if decision != "allow":
        return "not_run_guard_unavailable"
    return _auto_offline_status(row)


def _technical_issue(row):
    """Whether a result belongs in the technical-failure view."""
    guard_state = row["guard_state"] or ""
    auto_state = row["auto_state"] or ""
    return (
        row["job_state"] == "deferred"
        or
        row["review_state"] == "failed"
        or guard_state in {"unavailable", "http_error", "invalid"}
        or auto_state in {"unavailable", "http_error", "invalid"}
        or (row["review_state"] and not guard_state)
        or (row["review_state"] and not auto_state)
    )


def _state_label(value):
    return {
        "complete": "已完成",
        "pending": "待分析",
        "running": "分析中",
        "unavailable": "待重试",
        "failed": "失败",
        "deferred": "已暂停重试",
        "unreviewed": "未分析",
    }.get(value, value or "未分析")


class ReviewStore:
    """Read analysis/source data and write only human labels."""

    def __init__(self, analysis_db, labels_db=None, stores=None, gray_lanes=None, diagnostic_manifest=None):
        self.analysis_db = Path(analysis_db).expanduser()
        if not self.analysis_db.is_absolute() or self.analysis_db.is_symlink():
            raise ValueError("analysis_db_must_be_absolute_non_symlink")
        self.labels_db = Path(labels_db or self.analysis_db.with_name("review-labels.sqlite"))
        if not self.labels_db.is_absolute() or self.labels_db.is_symlink():
            raise ValueError("labels_db_must_be_absolute_non_symlink")
        self.diagnostic_manifest = Path(
            diagnostic_manifest or self.analysis_db.with_name("diagnostic-200.json")
        ).expanduser()
        if not self.diagnostic_manifest.is_absolute() or self.diagnostic_manifest.is_symlink():
            raise ValueError("diagnostic_manifest_must_be_absolute_non_symlink")
        self.stores = {}
        for region, root in (stores or {}).items():
            root = Path(root).expanduser()
            if not root.is_absolute() or root.is_symlink():
                raise ValueError("store_root_must_be_absolute_non_symlink")
            self.stores[str(region)] = root
        self.gray_lanes = dict(DEFAULT_GRAY_LANES)
        if gray_lanes:
            self.gray_lanes.update({str(region): str(port) for region, port in gray_lanes.items()})
        self._labels_lock = threading.Lock()
        self._ensure_labels()

    def _diagnostic(self):
        """Read the small body-free diagnostic manifest, if present."""
        try:
            value = json.loads(self.diagnostic_manifest.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"schema": None, "set_id": None, "created_at": None, "rows": [], "counts": {}}
        except (OSError, ValueError, TypeError):
            raise OSError("diagnostic_manifest_unavailable")
        if not isinstance(value, dict) or value.get("schema") != "work-observation-diagnostic-v1":
            raise ValueError("invalid_diagnostic_manifest")
        rows = value.get("rows")
        if not isinstance(rows, list):
            raise ValueError("invalid_diagnostic_manifest_rows")
        if len(rows) > 500:
            raise ValueError("diagnostic_manifest_too_large")
        safe_rows = []
        allowed = {
            "rank", "region", "event_id", "at", "ingress", "source_sha",
            "client", "protocol", "outcome", "requested_model", "actual_model",
            "job_state", "attempts", "review_state", "guard_state",
            "guard_decision", "auto_state", "auto_model", "selection_bucket",
            "selection_reason",
        }
        feature_keys = {
            "message_count", "tool_count", "attachment_count",
            "request_bytes", "response_bytes", "flags",
        }
        for row in rows:
            if not isinstance(row, dict) or not isinstance(row.get("region"), str) or not isinstance(row.get("event_id"), str):
                continue
            safe = {key: row.get(key) for key in allowed if key in row}
            features = row.get("features")
            if isinstance(features, dict):
                safe["features"] = {
                    key: features.get(key)
                    for key in feature_keys
                    if key in features
                }
            safe_rows.append(safe)
        return {
            "schema": value.get("schema"),
            "set_id": value.get("set_id"),
            "created_at": value.get("created_at"),
            "rows": safe_rows,
            "counts": value.get("counts") if isinstance(value.get("counts"), dict) else {},
        }

    @contextmanager
    def _analysis(self):
        uri = "file:" + quote(str(self.analysis_db), safe="") + "?mode=ro"
        # The rolling worker commits a semantic batch in bounded chunks.  Keep
        # the read side patient so a refresh during that commit does not turn
        # into a misleading "data unavailable" screen.
        db = sqlite3.connect(uri, uri=True, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=10000")
            # Human labels live in a separate writable database.  Attach it
            # read only for filtering/counting the queue, so the analysis
            # connection can never mutate either source while a reviewer is
            # saving a label.
            labels_uri = "file:" + quote(str(self.labels_db), safe="") + "?mode=ro"
            db.execute("ATTACH DATABASE ? AS review_labels", (labels_uri,))
            yield db
        finally:
            db.close()

    def _ensure_labels(self):
        self.labels_db.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self._labels_lock:
            db = sqlite3.connect(self.labels_db, timeout=2)
            try:
                db.execute("PRAGMA journal_mode=WAL")
                db.execute("PRAGMA busy_timeout=2000")
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS human_reviews (
                        region TEXT NOT NULL,
                        event_id TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'needs_review',
                        guard_label TEXT,
                        auto_label TEXT,
                        notes TEXT NOT NULL DEFAULT '',
                        reviewer TEXT NOT NULL DEFAULT 'local',
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY(region, event_id)
                    );
                    CREATE INDEX IF NOT EXISTS human_reviews_updated
                    ON human_reviews(updated_at);
                    """
                )
                db.commit()
                os.chmod(self.labels_db, 0o600)
            finally:
                db.close()

    def _labels(self, keys):
        if not keys:
            return {}
        db = sqlite3.connect(self.labels_db, timeout=10)
        try:
            # Avoid tuple-IN syntax: the GPU image carries an older SQLite
            # build where ``(a,b) IN ((?,?))`` is parsed as a row misuse.
            marks = " OR ".join("(region=? AND event_id=?)" for _ in keys)
            params = [part for key in keys for part in key]
            rows = db.execute(
                f"SELECT region,event_id,status,guard_label,auto_label,notes,reviewer,updated_at "
                f"FROM human_reviews WHERE {marks}",
                params,
            ).fetchall()
            return {(row[0], row[1]): self._label_row(row) for row in rows}
        finally:
            db.close()

    @staticmethod
    def _label_row(row):
        return {
            "status": row[2],
            "guard_label": row[3],
            "auto_label": row[4],
            "notes": row[5],
            "reviewer": row[6],
            "updated_at": row[7],
        }

    def _source(self, region, source_path, expected_sha=None):
        root = self.stores.get(region)
        if root is None or not source_path:
            return None, {"verified": False, "reason": "source_root_not_configured"}
        path = Path(source_path)
        try:
            resolved_root = root.resolve(strict=True)
            resolved = path.resolve(strict=False)
            if resolved_root != resolved and resolved_root not in resolved.parents:
                return None, {"verified": False, "reason": "source_outside_configured_root"}
            if path.is_symlink():
                return None, {"verified": False, "reason": "source_symlink_refused"}
            event, digest = rolling.read_record(path)
            if expected_sha and digest != expected_sha:
                return None, {"verified": False, "reason": "source_digest_mismatch"}
            return event, {"verified": True, "sha256": digest, "path": str(path)}
        except (OSError, ValueError, KeyError, TypeError):
            return None, {"verified": False, "reason": "source_unavailable_or_invalid"}

    def _source_fields(self, row):
        event, integrity = self._source(row["region"], row["source_path"], row["source_sha"])
        if event is None:
            return {"integrity": integrity, "messages": [], "task_preview": "（源记录暂不可读）"}
        messages = _message_view(event)
        return {
            "integrity": integrity,
            "messages": messages,
            "task_preview": _task_preview(messages),
            "client": event.get("client"),
            "protocol": event.get("protocol"),
            "kind": event.get("kind"),
            "outcome": event.get("outcome"),
            "missing": _safe_json(event.get("missing", [])),
            "attachments": _safe_json((event.get("request") or {}).get("attachments", []))
            if isinstance(event.get("request"), dict)
            else [],
        }

    def _latest_run(self):
        """Read only bounded, body-free worker metadata for the header."""
        path = self.analysis_db.with_name("tick.json")
        try:
            value = _safe_json(json.loads(path.read_text(encoding="utf-8")))
            if not isinstance(value, dict):
                return None
            # Keep the UI contract stable even with an older tick file.
            value.setdefault("run_id", value.get("at", "")[:19].replace("-", "").replace(":", "").replace("T", "-") if isinstance(value.get("at"), str) else None)
            return value
        except (OSError, ValueError, TypeError):
            return None

    def _review_row(self, row, labels, source, diagnostic=None):
        state = _job_state(row)
        guard_categories = _json(row["guard_categories"])
        guard_reasons = _json(row["guard_reason_codes"])
        auto_classification = _json(row["auto_classification"])
        guard_display = _guard_display(row)
        auto_display = _auto_display(row)
        auto_offline_status = _auto_offline_status(row)
        auto_online_status = _auto_online_status(row)
        technical_issue = _technical_issue(row)
        human = labels.get((row["region"], row["event_id"]))
        human_status = (human or {}).get("status") or row["human_status"] or "needs_review"
        return {
            "region": row["region"],
            "event_id": row["event_id"],
            "at": row["at"],
            "ingress": row["ingress"],
            "client": row["client"],
            "model": row["model"],
            "requested_model": row["requested_model"],
            "reported_model": row["reported_model"],
            "protocol": row["protocol"],
            "outcome": row["outcome"],
            "status": state,
            "status_label": _state_label(state),
            "attempts": row["attempts"] or 0,
            "guard": {
                "state": row["guard_state"] or "not_run",
                "decision": row["guard_decision"],
                "risk_level": row["guard_risk_level"],
                "categories": guard_categories if isinstance(guard_categories, list) else [],
                "reason_codes": guard_reasons if isinstance(guard_reasons, list) else [],
                "http_status": row["guard_http_status"],
                "display": guard_display,
            },
            "auto": {
                "state": row["auto_state"] or "not_run",
                "model": row["auto_model"],
                "effort": row["auto_effort"],
                "action": row["auto_action"],
                "reason": row["auto_reason"],
                "classification": auto_classification if isinstance(auto_classification, dict) else {},
                "http_status": row["auto_http_status"],
                "display": auto_display,
                "offline_status": auto_offline_status,
                "online_status": auto_online_status,
                "offline_label": {
                    "selected": "离线已选模型",
                    "blocked": "离线被 Auto 拒绝",
                    "technical_failure": "离线技术失败",
                    "not_run": "离线未运行",
                }[auto_offline_status],
            },
            "production": {
                "guard": row["guard_decision"] or ("unavailable" if row["guard_state"] else "not_run"),
                "auto": auto_online_status,
            },
            "analysis": {
                "job_state": row["job_state"],
                "review_state": row["review_state"],
                "job_status_label": _state_label(row["job_state"] or "unreviewed"),
                "technical_issue": technical_issue,
            },
            "diagnostic": diagnostic,
            "error_code": row["error_code"],
            "reviewed_at": row["reviewed_at"],
            "human_status": human_status,
            "human": human,
            "gray_ingress": self.gray_lanes.get(row["region"]),
            "formal_ingress": row["ingress"] or DEFAULT_FORMAL_LANES.get(row["region"]),
            "analysis_plane": "offline_analysis",
            **source,
        }

    @staticmethod
    def _base_sql():
        return """
            SELECT
              COALESCE(sr.region, j.region) AS region,
              COALESCE(sr.event_id, j.event_id) AS event_id,
              COALESCE(sr.source_path, j.source_path) AS source_path,
              COALESCE(sr.source_sha, j.sha) AS source_sha,
              -- Keep the original capture time stable. Using reviewed_at here
              -- would move a row between pages when somebody labels it.
              j.at AS at,
              j.state AS job_state, j.attempts AS attempts,
              sr.state AS review_state,
              e.ingress AS ingress, e.client AS client, e.model AS model,
              e.requested_model AS requested_model, e.reported_model AS reported_model,
              e.protocol AS protocol, e.outcome AS outcome,
              sr.guard_state AS guard_state, sr.guard_decision AS guard_decision,
              sr.guard_risk_level AS guard_risk_level, sr.guard_categories AS guard_categories,
              sr.guard_reason_codes AS guard_reason_codes, sr.guard_http_status AS guard_http_status,
              sr.auto_state AS auto_state, sr.auto_model AS auto_model,
              sr.auto_effort AS auto_effort, sr.auto_action AS auto_action,
              sr.auto_reason AS auto_reason, sr.auto_classification AS auto_classification,
              sr.auto_http_status AS auto_http_status, sr.error_code AS error_code,
              sr.reviewed_at AS reviewed_at,
              hr.status AS human_status
            FROM review_jobs j
            LEFT JOIN semantic_reviews sr ON sr.region=j.region AND sr.event_id=j.event_id
            LEFT JOIN events e ON e.region=j.region AND e.id=j.event_id
            LEFT JOIN review_labels.human_reviews hr ON hr.region=COALESCE(sr.region,j.region)
              AND hr.event_id=COALESCE(sr.event_id,j.event_id)
        """

    def list_reviews(self, *, limit=50, offset=0, page=None, region=None, status=None,
                     query=None, view="review", human_status=None):
        limit = min(max(int(limit), 1), MAX_PAGE_SIZE)
        if page is not None:
            offset = (max(int(page), 1) - 1) * limit
        else:
            offset = max(int(offset), 0)
        view = str(view or "review")
        if view not in VALID_REVIEW_VIEWS:
            raise ValueError("invalid_review_view")
        if human_status is None:
            # The default work queue contains only blocks which have not been
            # handled yet. Other views remain historical/diagnostic views.
            human_status = "needs_review" if view == "review" else "all"
        human_status = str(human_status)
        if human_status not in VALID_HUMAN_STATUS_FILTERS:
            raise ValueError("invalid_human_status")
        clauses, params = ["e.kind='http_exchange'"], []
        diagnostic_map = {}
        diagnostic_info = None
        if view == "diagnostic":
            diagnostic_info = self._diagnostic()
            diagnostic_map = {
                (row["region"], row["event_id"]): row
                for row in diagnostic_info["rows"]
            }
            if not diagnostic_map:
                clauses.append("1=0")
            else:
                marks = " OR ".join("(j.region=? AND j.event_id=?)" for _ in diagnostic_map)
                clauses.append("(" + marks + ")")
                params.extend(part for key in diagnostic_map for part in key)
        # The operator views intentionally answer different questions:
        # backlog is work not yet consumed by semantic analysis, review is the
        # explicit Guard block queue, auto is the set that received an offline
        # Auto response, and technical isolates transport/invalid results.
        # Keep these predicates server-side so a page cannot accidentally mix
        # pending work or classifier failures into a model-choice queue.
        if view == "backlog":
            clauses.append("j.state IN ('pending','running')")
        elif view == "auto":
            clauses.append("sr.auto_state IN ('complete','blocked')")
        elif view == "technical":
            clauses.append("(" + " OR ".join([
                "sr.state='failed'",
                "j.state='deferred'",
                "sr.guard_state IN ('unavailable','http_error','invalid')",
                "sr.auto_state IN ('unavailable','http_error','invalid')",
                "(sr.state IS NOT NULL AND sr.guard_state IS NULL)",
                "(sr.state IS NOT NULL AND sr.auto_state IS NULL)",
            ]) + ")")
        elif view == "diagnostic":
            # The manifest predicate above is the complete scope.  Keep the
            # regular status and region filters available for inspection.
            pass
        elif view == "review":
            clauses.append("sr.guard_decision='block'")
        elif view == "all":
            clauses.append("sr.state IS NOT NULL")
        if human_status != "all":
            clauses.append("COALESCE(hr.status,'needs_review')=?")
            params.append(human_status)
        if region:
            clauses.append("COALESCE(sr.region,j.region)=?")
            params.append(region)
        if status and status != "all":
            clauses.append("COALESCE(sr.state,j.state,'unreviewed')=?")
            params.append(status)
        if query:
            like = "%" + query[:120] + "%"
            clauses.append("(j.event_id LIKE ? OR e.client LIKE ? OR e.model LIKE ? OR e.requested_model LIKE ? OR sr.auto_model LIKE ?)")
            params.extend([like] * 5)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        if view == "backlog":
            order = "j.at ASC,event_id ASC"
        elif view == "diagnostic":
            order = "j.at ASC,event_id ASC"
        elif view == "review":
            order = "j.at DESC,event_id DESC"
        elif view == "technical":
            order = "j.at DESC,event_id DESC"
        else:
            order = "j.at DESC,event_id DESC"
        with self._analysis() as db:
            count_row = db.execute(
                "SELECT COUNT(*) FROM (" + self._base_sql() + where + ")",
                params,
            ).fetchone()
            total = int(count_row[0] if count_row else 0)
            rows = db.execute(
                self._base_sql() + where + " ORDER BY " + order + " LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        keys = [(row["region"], row["event_id"]) for row in rows[:limit]]
        labels = self._labels(keys)
        result = []
        for row in rows[:limit]:
            source = self._source_fields(row)
            # List view receives only the bounded task preview. Full messages
            # are fetched by the detail endpoint.
            source.pop("messages", None)
            result.append(self._review_row(row, labels, source, diagnostic_map.get((row["region"], row["event_id"]))))
        page = (offset // limit) + 1
        pages = (total + limit - 1) // limit if total else 0
        start = offset + 1 if result else 0
        end = offset + len(result)
        return {
            "reviews": result,
            "view": view,
            "human_status": human_status,
            "total": total,
            "page": page,
            "pages": pages,
            "start": start,
            "end": end,
            "has_prev": offset > 0,
            "has_more": offset + len(result) < total,
            "next_offset": offset + len(result) if offset + len(result) < total else None,
            "page_count": pages,
            "offset": offset,
            "limit": limit,
            "diagnostic_set": {
                "set_id": diagnostic_info["set_id"],
                "created_at": diagnostic_info["created_at"],
                "counts": diagnostic_info["counts"],
            } if diagnostic_info is not None else None,
        }

    def get_review(self, region, event_id):
        if not EVENT_ID.fullmatch(event_id):
            raise ValueError("invalid_event_id")
        with self._analysis() as db:
            row = db.execute(self._base_sql() + " WHERE e.kind='http_exchange' AND j.region=? AND j.event_id=?", (region, event_id)).fetchone()
        if row is None:
            raise KeyError("review_not_found")
        labels = self._labels([(region, event_id)])
        diagnostic = self._diagnostic()
        diagnostic_map = {(item["region"], item["event_id"]): item for item in diagnostic["rows"]}
        return self._review_row(row, labels, self._source_fields(row), diagnostic_map.get((region, event_id)))

    def summary(self):
        with self._analysis() as db:
            total = db.execute("SELECT COUNT(*) FROM review_jobs j JOIN events e ON e.region=j.region AND e.id=j.event_id WHERE e.kind='http_exchange'").fetchone()[0]
            pending = db.execute("SELECT COUNT(*) FROM review_jobs j JOIN events e ON e.region=j.region AND e.id=j.event_id WHERE e.kind='http_exchange' AND j.state IN ('pending','running')").fetchone()[0]
            failed = db.execute("SELECT COUNT(*) FROM review_jobs j JOIN events e ON e.region=j.region AND e.id=j.event_id WHERE e.kind='http_exchange' AND j.state='failed'").fetchone()[0]
            retry_deferred = db.execute("SELECT COUNT(*) FROM review_jobs j JOIN events e ON e.region=j.region AND e.id=j.event_id WHERE e.kind='http_exchange' AND j.state='deferred'").fetchone()[0]
            complete = db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE state='complete'").fetchone()[0]
            semantic_total = db.execute("SELECT COUNT(*) FROM semantic_reviews").fetchone()[0]
            auto_with_model = db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE auto_model IS NOT NULL AND auto_model <> ''").fetchone()[0]
            auto_attempted = db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE auto_state IN ('complete','blocked')").fetchone()[0]
            auto_blocked = db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE auto_state='blocked'").fetchone()[0]
            auto_unavailable = db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE auto_state='unavailable'").fetchone()[0]
            auto_technical = db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE auto_state IN ('unavailable','http_error','invalid')").fetchone()[0]
            auto_not_run = db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE auto_state IS NULL OR auto_state='not_run'").fetchone()[0]
            guard_unavailable = db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE guard_state='unavailable'").fetchone()[0]
            guard_block = db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE guard_decision='block'").fetchone()[0]
            guard_review = db.execute("""SELECT COUNT(*) FROM semantic_reviews sr
                LEFT JOIN review_labels.human_reviews hr ON hr.region=sr.region AND hr.event_id=sr.event_id
                WHERE sr.guard_decision='block' AND COALESCE(hr.status,'needs_review')='needs_review'""").fetchone()[0]
            guard_allow = db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE guard_decision='allow'").fetchone()[0]
            guard_technical = db.execute("SELECT COUNT(*) FROM semantic_reviews WHERE guard_state IN ('unavailable','http_error','invalid') OR (guard_state IS NOT NULL AND guard_decision IS NULL)").fetchone()[0]
            technical_total = db.execute("""SELECT COUNT(*) FROM semantic_reviews WHERE
                state='failed'
                OR guard_state IN ('unavailable','http_error','invalid')
                OR auto_state IN ('unavailable','http_error','invalid')
                OR (state IS NOT NULL AND guard_state IS NULL)
                OR (state IS NOT NULL AND auto_state IS NULL)""").fetchone()[0]
            guard = dict(db.execute("SELECT COALESCE(guard_decision,'not_run'),COUNT(*) FROM semantic_reviews GROUP BY 1").fetchall())
            models = dict(db.execute("SELECT auto_model,COUNT(*) FROM semantic_reviews WHERE auto_state='complete' AND auto_model IS NOT NULL AND auto_model <> '' GROUP BY auto_model ORDER BY 2 DESC LIMIT 12").fetchall())
            last = db.execute("SELECT MAX(reviewed_at) FROM semantic_reviews").fetchone()[0]
        with sqlite3.connect(self.labels_db, timeout=2) as labels_db:
            labels_db.row_factory = sqlite3.Row
            label_total = labels_db.execute("SELECT COUNT(*) FROM human_reviews").fetchone()[0]
            label_status = dict(labels_db.execute("SELECT status,COUNT(*) FROM human_reviews GROUP BY status").fetchall())
            guard_labels = dict(labels_db.execute("SELECT COALESCE(guard_label,'unlabeled'),COUNT(*) FROM human_reviews GROUP BY 1").fetchall())
            auto_labels = dict(labels_db.execute("SELECT COALESCE(auto_label,'unlabeled'),COUNT(*) FROM human_reviews GROUP BY 1").fetchall())
        return {
            "service": "standalone_work_observation_review",
            "total_jobs": total,
            "pending_jobs": pending,
            "failed_jobs": failed,
            "deferred_jobs": retry_deferred,
            "complete_reviews": complete,
            "semantic_reviews_total": semantic_total,
            "auto_with_model": auto_with_model,
            "auto_attempted": auto_attempted,
            "auto_blocked": auto_blocked,
            "auto_unavailable": auto_unavailable,
            "auto_technical": auto_technical,
            "auto_not_run": auto_not_run,
            "guard_unavailable": guard_unavailable,
            "guard_review_total": guard_review,
            "guard_block_total": guard_block,
            "guard_allow_total": guard_allow,
            "guard_technical": guard_technical,
            "technical_total": technical_total,
            "auto_full_total": auto_attempted,
            "guard_decisions": guard,
            "auto_models": models,
            "last_reviewed_at": last,
            "human_labels": label_total,
            "human_status": label_status,
            "human_guard_labels": guard_labels,
            "human_auto_labels": auto_labels,
            "formal_lanes": DEFAULT_FORMAL_LANES,
            "gray_lanes": self.gray_lanes,
            "latest_run": self._latest_run(),
            "diagnostic_set": self._diagnostic_summary(),
            "updated_at": _now(),
        }

    def _diagnostic_summary(self):
        value = self._diagnostic()
        return {
            "set_id": value["set_id"],
            "created_at": value["created_at"],
            "counts": value["counts"],
            "available": bool(value["rows"]),
        }

    def save_label(self, region, event_id, payload):
        if not isinstance(payload, dict):
            raise ValueError("json_object_required")
        status = payload.get("status", "reviewed")
        guard_label = payload.get("guard_label")
        auto_label = payload.get("auto_label")
        notes = payload.get("notes", "")
        reviewer = payload.get("reviewer", "local")
        if status not in VALID_REVIEW_STATUS:
            raise ValueError("invalid_review_status")
        if guard_label is not None and guard_label not in VALID_GUARD_LABELS:
            raise ValueError("invalid_guard_label")
        if auto_label is not None and auto_label not in VALID_AUTO_LABELS:
            raise ValueError("invalid_auto_label")
        if not isinstance(notes, str) or len(notes) > 4000:
            raise ValueError("notes_too_long")
        if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120:
            raise ValueError("invalid_reviewer")
        # Verify the review exists before accepting a label.
        self.get_review(region, event_id)
        at = _now()
        with self._labels_lock:
            db = sqlite3.connect(self.labels_db, timeout=2)
            try:
                db.execute(
                    """INSERT INTO human_reviews(region,event_id,status,guard_label,auto_label,notes,reviewer,updated_at)
                    VALUES(?,?,?,?,?,?,?,?)
                    ON CONFLICT(region,event_id) DO UPDATE SET status=excluded.status,
                    guard_label=excluded.guard_label,auto_label=excluded.auto_label,
                    notes=excluded.notes,reviewer=excluded.reviewer,updated_at=excluded.updated_at""",
                    (region, event_id, status, guard_label, auto_label, notes, reviewer.strip(), at),
                )
                db.commit()
            finally:
                db.close()
        return self.get_review(region, event_id)


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "WorkObservationReview/1.0"

    @property
    def store(self):
        return self.server.review_store

    @property
    def static_root(self):
        return self.server.static_root

    def log_message(self, fmt, *args):
        # Keep request logs metadata-only; never print query bodies or payloads.
        super().log_message("%s", fmt % args)

    def _send_json(self, value, status=HTTPStatus.OK):
        body = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status, code):
        self._send_json({"error": code}, status)

    def _body(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            raise ValueError("invalid_content_length")
        if length < 0 or length > MAX_REQUEST_BYTES:
            raise ValueError("request_body_too_large")
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid_json") from exc

    def do_GET(self):  # noqa: N802
        parsed = urlsplit(self.path)
        try:
            if parsed.path in {"/api/health", "/healthz"}:
                self._send_json({"status": "ok", "service": self.server_version, "updated_at": _now()})
                return
            if parsed.path == "/api/summary":
                self._send_json(self.store.summary())
                return
            if parsed.path == "/api/reviews":
                query = parse_qs(parsed.query)
                result = self.store.list_reviews(
                    limit=int(query.get("limit", [50])[0]),
                    page=int(query.get("page", [1])[0]) if "page" in query else None,
                    offset=int(query.get("offset", [0])[0]),
                    region=query.get("region", [None])[0] or None,
                    status=query.get("status", [None])[0] or None,
                    query=query.get("q", [None])[0] or None,
                    view=query.get("view", ["review"])[0] or "review",
                    human_status=query.get("human_status", [None])[0] or None,
                )
                self._send_json(result)
                return
            if parsed.path.startswith("/api/reviews/"):
                pieces = [unquote(piece) for piece in parsed.path.split("/") if piece]
                if len(pieces) == 4 and pieces[0:2] == ["api", "reviews"]:
                    self._send_json(self.store.get_review(pieces[2], pieces[3]))
                    return
            self._static(parsed.path)
        except (ValueError, TypeError):
            self._error(HTTPStatus.BAD_REQUEST, "invalid_request")
        except KeyError:
            self._error(HTTPStatus.NOT_FOUND, "review_not_found")
        except (OSError, sqlite3.Error):
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "dashboard_data_unavailable")

    def do_POST(self):  # noqa: N802
        parsed = urlsplit(self.path)
        if not parsed.path.startswith("/api/reviews/") or not parsed.path.endswith("/label"):
            self._error(HTTPStatus.NOT_FOUND, "endpoint_not_found")
            return
        pieces = [unquote(piece) for piece in parsed.path.split("/") if piece]
        if len(pieces) != 5 or pieces[0:2] != ["api", "reviews"] or pieces[4] != "label":
            self._error(HTTPStatus.NOT_FOUND, "endpoint_not_found")
            return
        try:
            result = self.store.save_label(pieces[2], pieces[3], self._body())
            self._send_json(result)
        except (ValueError, TypeError):
            self._error(HTTPStatus.BAD_REQUEST, "invalid_label")
        except KeyError:
            self._error(HTTPStatus.NOT_FOUND, "review_not_found")
        except (OSError, sqlite3.Error):
            self._error(HTTPStatus.SERVICE_UNAVAILABLE, "label_store_unavailable")

    def _static(self, path):
        relative = unquote(path.lstrip("/")) or "index.html"
        candidate = (self.static_root / relative).resolve(strict=False)
        root = self.static_root.resolve(strict=True)
        if candidate != root and root not in candidate.parents:
            self._error(HTTPStatus.NOT_FOUND, "asset_not_found")
            return
        if not candidate.is_file() or candidate.is_symlink():
            self._error(HTTPStatus.NOT_FOUND, "asset_not_found")
            return
        content = candidate.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mimetypes.guess_type(str(candidate))[0] or "application/octet-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis-db", required=True, help="rolling analysis index.sqlite")
    parser.add_argument("--store", action="append", default=[], metavar="REGION=PATH", help="source store root; repeat per region")
    parser.add_argument("--labels-db", help="separate human labels SQLite path")
    parser.add_argument("--diagnostic-manifest", help="body-free diagnostic set manifest (defaults beside analysis DB)")
    parser.add_argument("--static-root", default=str(Path(__file__).parents[1] / "review"))
    parser.add_argument("--host", default="127.0.0.1", help="bind address; loopback is the safe default")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--gray-lane", action="append", default=[], metavar="REGION=PORT",
                        help="gray test lane shown in the UI; repeat per region (defaults tokyo=4004,us=4005)")
    return parser


def parse_stores(values):
    stores = {}
    for value in values:
        if "=" not in value:
            raise ValueError("store_must_be_REGION_equals_PATH")
        region, path = value.split("=", 1)
        if not region or not path:
            raise ValueError("store_must_be_REGION_equals_PATH")
        stores[region] = path
    return stores


def parse_gray_lanes(values):
    lanes = {}
    for value in values:
        if "=" not in value:
            raise ValueError("gray_lane_must_be_REGION_equals_PORT")
        region, port = value.split("=", 1)
        if not region or not port.isdigit() or not 1 <= int(port) <= 65535:
            raise ValueError("gray_lane_must_be_REGION_equals_PORT")
        lanes[region] = port
    return lanes


def main(argv=None):
    args = build_parser().parse_args(argv)
    if not 1 <= args.port <= 65535:
        raise SystemExit("invalid_port")
    static_root = Path(args.static_root).resolve()
    if not static_root.is_dir():
        raise SystemExit("static_root_not_found")
    try:
        store = ReviewStore(
            args.analysis_db,
            args.labels_db,
            parse_stores(args.store),
            parse_gray_lanes(args.gray_lane),
            args.diagnostic_manifest,
        )
    except (OSError, ValueError, sqlite3.Error) as exc:
        raise SystemExit(str(exc))
    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    server.review_store = store
    server.static_root = static_root
    print(f"work-observation review dashboard listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
