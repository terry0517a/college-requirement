import httpx, pytest
from collegedata.cac_http import CacFetcher, BusyError, make_ssl_context, USER_AGENT

class Clock:
    def __init__(self): self.t = 0.0; self.slept = []
    def now(self): return self.t
    def sleep(self, s): self.slept.append(s); self.t += s

def _fetcher(clock, **kw):
    return CacFetcher(httpx.Client(headers={"User-Agent": USER_AGENT}), min_interval=3.0, sleep=clock.sleep, clock=clock.now, **kw)

def test_ssl_context_includes_twca_intermediate():
    ctx = make_ssl_context()
    subjects = [tuple(x[0] for x in c["subject"]) for c in ctx.get_ca_certs()]
    assert any(("commonName", "TWCA SSL Certification Authority") in s for s in subjects)

def test_get_spaces_requests_by_three_seconds(httpx_mock):
    httpx_mock.add_response(url="https://www.cac.edu.tw/a", text="a")
    httpx_mock.add_response(url="https://www.cac.edu.tw/b", text="b")
    clock = Clock(); f = _fetcher(clock)
    f.get("https://www.cac.edu.tw/a"); f.get("https://www.cac.edu.tw/b")
    assert sum(clock.slept) >= 3.0 and f.requests_made == 2
    assert httpx_mock.get_requests()[0].headers["User-Agent"] == USER_AGENT

def test_busy_page_raises(httpx_mock):
    httpx_mock.add_response(url="https://www.cac.edu.tw/x", text="<html>流量過大，請稍後再試。</html>")
    with pytest.raises(BusyError):
        _fetcher(Clock()).get("https://www.cac.edu.tw/x")

def test_503_raises_busy(httpx_mock):
    httpx_mock.add_response(url="https://www.cac.edu.tw/x", status_code=503)
    with pytest.raises(BusyError):
        _fetcher(Clock()).get("https://www.cac.edu.tw/x")

def test_download_resumes_after_timeout(httpx_mock):
    url = "https://www.cac.edu.tw/p.png"
    httpx_mock.add_response(url=url, status_code=200, content=b"ABCDEFGHIJ", headers={"Content-Length": "10"})
    f = _fetcher(Clock())
    assert f.download(url) == b"ABCDEFGHIJ"

def test_download_retries_transport_error_with_range(httpx_mock):
    url = "https://www.cac.edu.tw/p.png"
    httpx_mock.add_exception(httpx.ReadTimeout("slow"), url=url)
    httpx_mock.add_response(url=url, status_code=206, content=b"ABCDEFGHIJ",
                            headers={"Content-Range": "bytes 0-9/10"}, match_headers={"Range": "bytes=0-"})
    assert _fetcher(Clock()).download(url) == b"ABCDEFGHIJ"

def test_download_gives_up_after_max_attempts(httpx_mock):
    url = "https://www.cac.edu.tw/p.png"
    for _ in range(2):
        httpx_mock.add_exception(httpx.ReadTimeout("slow"), url=url)
    with pytest.raises(httpx.ReadTimeout):
        _fetcher(Clock()).download(url, max_attempts=2)
