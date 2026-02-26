from __future__ import annotations

import json
import logging
import os
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Lock
from typing import Any, Awaitable, Callable, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

_request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_logger_configured = False


class JSONLogFormatter(logging.Formatter):
    def format(
        self, record: logging.LogRecord
    ) -> str:  # pragma: no cover - logging glue
        payload = getattr(record, "payload", None)
        log: Dict[str, Any] = {
            "timestamp": datetime.utcnow()
            .replace(tzinfo=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "level": record.levelname.lower(),
            "logger": record.name,
        }

        request_id = getattr(record, "request_id", None)
        if request_id:
            log["request_id"] = request_id

        if isinstance(payload, dict):
            log.update(payload)
        else:
            log["message"] = record.getMessage()

        if "message" not in log:
            log["message"] = record.getMessage()

        if record.exc_info:
            log["exception"] = self.formatException(record.exc_info)

        return json.dumps(log, ensure_ascii=True)


def get_request_id() -> str:
    request_id = _request_id_ctx.get()
    if not request_id:
        request_id = uuid4().hex
        _request_id_ctx.set(request_id)
    return request_id


def _resolve_log_path() -> Path:
    base = os.getenv("API_LOG_DIR")
    if base:
        base_path = Path(base)
    else:
        base_path = Path(__file__).resolve().parent / "logs"
    base_path.mkdir(parents=True, exist_ok=True)
    filename = os.getenv("API_LOG_FILENAME", "api.log")
    return base_path / filename


def configure_logging() -> None:  # pragma: no cover - side-effect function
    global _logger_configured
    if _logger_configured:
        return

    log_path = _resolve_log_path()
    handler = RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    formatter = JSONLogFormatter()
    handler.setFormatter(formatter)

    for logger_name in ("song_rec_api", "song_rec_api.requests"):
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.propagate = False

    # keep uvicorn errors readable on stderr while still capturing our own logs
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)

    _logger_configured = True


class RequestMetrics:
    def __init__(self) -> None:
        self._lock = Lock()
        self._total_requests = 0
        self._total_failures = 0
        self._latency_ms_sum = 0.0
        self._per_path: Dict[str, Dict[str, float]] = {}

    def record(self, path: str, status_code: int, latency_ms: float) -> None:
        with self._lock:
            self._total_requests += 1
            if status_code >= 500:
                self._total_failures += 1
            self._latency_ms_sum += latency_ms

            per_path = self._per_path.setdefault(
                path, {"count": 0, "avg_latency_ms": 0.0, "last_status": 0}
            )
            per_path["count"] += 1
            # incremental average to avoid dividing later
            per_path["avg_latency_ms"] += (
                latency_ms - per_path["avg_latency_ms"]
            ) / per_path["count"]
            per_path["last_status"] = status_code

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            avg_latency = (
                self._latency_ms_sum / self._total_requests
                if self._total_requests
                else 0.0
            )
            per_path_copy = {
                path: {
                    "count": stats["count"],
                    "avg_latency_ms": round(stats["avg_latency_ms"], 3),
                    "last_status": stats["last_status"],
                }
                for path, stats in self._per_path.items()
            }
            return {
                "total_requests": self._total_requests,
                "total_failures": self._total_failures,
                "avg_latency_ms": round(avg_latency, 3),
                "per_path": per_path_copy,
            }


class ObservabilityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, metrics: RequestMetrics) -> None:
        super().__init__(app)
        self._metrics = metrics
        self._logger = logging.getLogger("song_rec_api.requests")

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid4().hex
        token = _request_id_ctx.set(request_id)
        start_time = time.perf_counter()
        response: Optional[Response] = None
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        except HTTPException as exc:
            status_code = exc.status_code
            self._logger.warning(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "payload": {
                        "method": request.method,
                        "path": request.url.path,
                        "status": status_code,
                        "detail": exc.detail,
                    },
                },
            )
            raise
        except Exception:
            self._logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "payload": {
                        "method": request.method,
                        "path": request.url.path,
                    },
                },
            )
            raise
        finally:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.record(request.url.path, status_code, duration_ms)

            log_payload = {
                "event": "request_completed",
                "method": request.method,
                "path": request.url.path,
                "status": status_code,
                "duration_ms": round(duration_ms, 3),
                "client_ip": request.client.host if request.client else None,
            }
            self._logger.info(
                "request_completed",
                extra={"request_id": request_id, "payload": log_payload},
            )

            if response is not None:
                response.headers["X-Request-ID"] = request_id

            _request_id_ctx.reset(token)


def setup_observability(app: FastAPI) -> None:  # pragma: no cover - glue code
    if getattr(app.state, "_observability_initialized", False):
        return

    metrics = RequestMetrics()
    app.add_middleware(ObservabilityMiddleware, metrics=metrics)

    @app.get("/api/metrics", include_in_schema=False)
    def read_metrics():  # pragma: no cover - simple getter
        return metrics.snapshot()

    app.state.request_metrics = metrics
    app.state._observability_initialized = True
