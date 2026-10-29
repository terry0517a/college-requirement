"""HTTP layer for www.cac.edu.tw: TLS chain fix, throttling, resumable downloads, busy detection."""
import logging
import re
import ssl
import time
from pathlib import Path

import certifi
import httpx

log = logging.getLogger(__name__)

USER_AGENT = "collegedata-pipeline/0.1 (+https://github.com/terry0517a/college-requirement; cyw0517terry@gmail.com)"
CERT_PATH = Path(__file__).resolve().parents[2] / "config" / "certs" / "twca_ssl_sub_ca.pem"
BUSY_MARKER = "流量過大"
BUSY_STATUSES = (429, 503)
BUSY_PAGE_MAX_BYTES = 64 * 1024


class BusyError(Exception):
    """cac.edu.tw asked us to back off."""


def make_ssl_context() -> ssl.SSLContext:
    # The site does not send its intermediate cert, so add it to the standard bundle.
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.load_verify_locations(str(CERT_PATH))
    return ctx


def make_client(timeout: float = 120) -> httpx.Client:
    return httpx.Client(
        verify=make_ssl_context(),
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
        timeout=timeout,
    )


class CacFetcher:
    def __init__(self, client: httpx.Client, min_interval: float = 3.0,
                 sleep=time.sleep, clock=time.monotonic):
        self.client = client
        self.min_interval = min_interval
        self._sleep = sleep
        self._clock = clock
        self._last_request: float | None = None
        self.requests_made = 0

    def _throttle(self) -> None:
        if self._last_request is not None:
            wait = self.min_interval - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()
        self.requests_made += 1

    def _checked(self, url: str, response: httpx.Response) -> httpx.Response:
        if response.status_code in BUSY_STATUSES or BUSY_MARKER in response.text:
            raise BusyError(url)
        return response

    def get(self, url: str) -> httpx.Response:
        self._throttle()
        return self._checked(url, self.client.get(url))

    def post(self, url: str, data: dict) -> httpx.Response:
        self._throttle()
        return self._checked(url, self.client.post(url, data=data))

    def download(self, url: str, max_attempts: int = 6) -> bytes:
        buf = bytearray()
        last_error: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            self._throttle()
            try:
                with self.client.stream("GET", url, headers={"Range": f"bytes={len(buf)}-"}) as resp:
                    if resp.status_code in BUSY_STATUSES:
                        raise BusyError(url)
                    if resp.status_code == 416 and buf:
                        return bytes(buf)
                    resp.raise_for_status()
                    if resp.status_code == 200:
                        buf.clear()
                    base = len(buf)
                    for chunk in resp.iter_raw():
                        buf.extend(chunk)
                    received = bytes(buf[base:])
                    if len(received) < BUSY_PAGE_MAX_BYTES and BUSY_MARKER in received.decode("utf-8", "ignore"):
                        raise BusyError(url)
                    expected = _expected_total(resp, base)
                    if expected is None or len(buf) == expected:
                        return bytes(buf)
                    last_error = httpx.ReadError(f"incomplete download of {url}: {len(buf)}/{expected} bytes")
            except httpx.TransportError as exc:
                last_error = exc
            log.warning("download of %s incomplete (attempt %d/%d, %d bytes so far): %s",
                        url, attempt, max_attempts, len(buf), last_error)
        assert last_error is not None
        raise last_error


def _expected_total(resp: httpx.Response, base: int) -> int | None:
    content_range = resp.headers.get("Content-Range")
    if content_range:
        m = re.match(r"bytes\s+\d+-\d+/(\d+)", content_range)
        if m:
            return int(m.group(1))
    length = resp.headers.get("Content-Length")
    if length is not None and length.isdigit():
        return base + int(length)
    return None
