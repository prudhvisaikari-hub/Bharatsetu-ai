"""Structured Request Logging & Token-Bucket Rate Limiting Middleware.

Architectural Notes:
- Rate Limiting Scope: This in-memory rate limiter is per-process.
  For clustered, multi-worker, or distributed Kubernetes/Docker deployments,
  replace or back this with a shared Redis store (e.g. `redis-py` token-bucket).
- IP Extraction: Only honours `X-Forwarded-For` when `TRUSTED_PROXY=true`.
  Otherwise extracts `request.client.host` to prevent IP spoofing attacks.
- Memory Bounding: Automatically evicts stale IP buckets periodically so memory
  cannot grow without bound under scanner or brute-force traffic.
- Stricter Auth Limits: Limits `/api/auth/login` and `/api/auth/register` to 10 req/min/IP.
"""
import time
import uuid
import logging
from collections import defaultdict
from typing import Optional, List, Dict
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from . import config

logger = logging.getLogger("bharatsetu")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('{"time":"%(asctime)s", "level":"%(levelname)s", "msg":"%(message)s"}')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class TokenBucketRateLimiter:
    """Sliding-window in-memory rate limiter with automatic stale key eviction."""
    def __init__(self, requests_per_minute: int = 60):
        self.default_limit = requests_per_minute
        self.requests: Dict[str, List[float]] = defaultdict(list)
        self.last_cleanup = time.time()

    def is_allowed(self, client_ip: str, limit: Optional[int] = None) -> bool:
        max_allowed = limit if limit is not None else self.default_limit
        now = time.time()
        window_start = now - 60.0

        # Periodic eviction: purge empty or stale IP records every 300 seconds or when table > 1000 IPs
        if now - self.last_cleanup > 300.0 or len(self.requests) > 1000:
            stale = [ip for ip, timestamps in self.requests.items() if not timestamps or timestamps[-1] <= window_start]
            for ip in stale:
                del self.requests[ip]
            self.last_cleanup = now

        # Purge expired timestamps for current client
        self.requests[client_ip] = [t for t in self.requests[client_ip] if t > window_start]
        if len(self.requests[client_ip]) >= max_allowed:
            return False

        self.requests[client_ip].append(now)
        return True

# Global general route limiter
global_limiter = TokenBucketRateLimiter(requests_per_minute=config.RATE_LIMIT_PER_MINUTE)

# Strict limiter for authentication endpoints (prevents brute-force credential stuffing)
auth_limiter = TokenBucketRateLimiter(requests_per_minute=10)

class StructuredLoggingAndRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = str(uuid.uuid4())[:8]

        # Secure IP resolution: client IP only unless behind an explicitly trusted proxy
        if config.TRUSTED_PROXY and "x-forwarded-for" in request.headers:
            client_ip = request.headers["x-forwarded-for"].split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "127.0.0.1"

        # Check content-length header for upload size cap early
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > config.MAX_UPLOAD_BYTES:
                    logger.warning(f"request_id={req_id} ip={client_ip} path={request.url.path} status=413 msg=Content-Length exceeds 8 MB cap")
                    return Response(content='{"detail":"Upload exceeds 8 MB limit"}', status_code=413, media_type="application/json")
            except ValueError:
                pass

        # Static files and docs bypass rate limiting
        is_static = request.url.path.startswith("/static") or request.url.path in ("/favicon.ico",)

        if not is_static:
            # Stricter rate limits on authentication endpoints
            if request.url.path in ("/api/auth/login", "/api/auth/register"):
                if not auth_limiter.is_allowed(client_ip):
                    logger.warning(f"request_id={req_id} ip={client_ip} path={request.url.path} status=429 msg=Auth brute-force rate limit exceeded")
                    return Response(
                        content='{"detail":"Too many authentication attempts. Please try again in 1 minute."}',
                        status_code=429,
                        media_type="application/json"
                    )
            elif not global_limiter.is_allowed(client_ip):
                logger.warning(f"request_id={req_id} ip={client_ip} path={request.url.path} status=429 msg=Rate limit exceeded")
                return Response(
                    content='{"detail":"Rate limit exceeded. Please slow down."}',
                    status_code=429,
                    media_type="application/json"
                )

        start_time = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # Structured log without PII
        logger.info(
            f"req_id={req_id} ip={client_ip} method={request.method} "
            f"path={request.url.path} status={response.status_code} duration_ms={duration_ms}"
        )
        response.headers["X-Request-ID"] = req_id
        return response
