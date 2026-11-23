import time
import uuid
import logging
from collections import defaultdict
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from .config import RATE_LIMIT_PER_MINUTE, MAX_UPLOAD_BYTES

# Configure structured logging
logger = logging.getLogger("bharatsetu")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    formatter = logging.Formatter('{"time":"%(asctime)s", "level":"%(levelname)s", "msg":"%(message)s"}')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

class RateLimiter:
    def __init__(self, requests_per_minute: int = RATE_LIMIT_PER_MINUTE):
        self.limit = requests_per_minute
        self.requests = defaultdict(list)

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        window_start = now - 60.0
        # Clean older entries
        self.requests[client_ip] = [t for t in self.requests[client_ip] if t > window_start]
        if len(self.requests[client_ip]) >= self.limit:
            return False
        self.requests[client_ip].append(now)
        return True

rate_limiter = RateLimiter()

class StructuredLoggingAndRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = str(uuid.uuid4())[:8]
        client_ip = request.client.host if request.client else "127.0.0.1"

        # Check content-length header for upload size cap early
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_UPLOAD_BYTES:
            logger.warning(f"request_id={req_id} ip={client_ip} path={request.url.path} status=413 msg=Upload too large")
            return Response(content='{"detail":"Upload exceeds 8 MB limit"}', status_code=413, media_type="application/json")

        # Rate limit check (bypass docs / static if any)
        if not request.url.path.startswith("/static") and not rate_limiter.is_allowed(client_ip):
            logger.warning(f"request_id={req_id} ip={client_ip} path={request.url.path} status=429 msg=Rate limit exceeded")
            return Response(content='{"detail":"Rate limit exceeded. Please slow down."}', status_code=429, media_type="application/json")

        start_time = time.time()
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # Structured log
        logger.info(
            f"req_id={req_id} ip={client_ip} method={request.method} "
            f"path={request.url.path} status={response.status_code} duration_ms={duration_ms}"
        )
        response.headers["X-Request-ID"] = req_id
        return response
