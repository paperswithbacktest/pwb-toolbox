"""A deliberately slow HTTP client for scraping.

Two behaviours matter here and both are easy to get wrong:

* ``robots.txt`` is consulted before every request and cached per host. When
  the file cannot be retrieved because the server errored, the host is treated
  as fully disallowed rather than fully allowed -- an unreachable ``robots.txt``
  is not permission.
* Requests to the same host are spaced out by at least ``min_interval``
  seconds, or by the host's ``Crawl-delay`` when it advertises a longer one.

``sleep`` and ``monotonic`` are injectable so tests can exercise the pacing and
retry logic without spending real time.
"""

import threading
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests

DEFAULT_USER_AGENT = (
    "pwb-toolbox-scraper/0.1 " "(+https://github.com/paperswithbacktest/pwb-toolbox)"
)

#: Status codes worth retrying: rate limiting and transient server failures.
RETRY_STATUS = frozenset({429, 500, 502, 503, 504})


class RobotsDisallowed(RuntimeError):
    """Raised when ``robots.txt`` forbids the requested URL."""


def _origin(url: str) -> tuple[str, str]:
    parts = urlsplit(url)
    return parts.scheme, parts.netloc


class RobotsCache:
    """Fetches and caches ``robots.txt`` verdicts per origin."""

    def __init__(self, session, user_agent: str, timeout: float = 15.0):
        self._session = session
        self._user_agent = user_agent
        self._timeout = timeout
        self._parsers: dict[tuple[str, str], RobotFileParser] = {}
        self._lock = threading.Lock()

    def _fetch(self, origin: tuple[str, str]) -> RobotFileParser:
        scheme, netloc = origin
        parser = RobotFileParser()
        url = urlunsplit((scheme, netloc, "/robots.txt", "", ""))
        try:
            resp = self._session.get(
                url,
                timeout=self._timeout,
                headers={"User-Agent": self._user_agent},
            )
        except requests.RequestException:
            parser.disallow_all = True
            return parser

        if resp.status_code == 200:
            parser.parse(resp.text.splitlines())
        elif 400 <= resp.status_code < 500:
            # No robots.txt published: RFC 9309 says the host is unrestricted.
            parser.allow_all = True
        else:
            parser.disallow_all = True
        return parser

    def _parser_for(self, url: str) -> RobotFileParser:
        origin = _origin(url)
        with self._lock:
            parser = self._parsers.get(origin)
            if parser is None:
                parser = self._fetch(origin)
                self._parsers[origin] = parser
        return parser

    def can_fetch(self, url: str) -> bool:
        return self._parser_for(url).can_fetch(self._user_agent, url)

    def crawl_delay(self, url: str) -> float | None:
        delay = self._parser_for(url).crawl_delay(self._user_agent)
        return None if delay is None else float(delay)


class PoliteSession:
    """Rate-limited, robots-aware wrapper around a ``requests`` session."""

    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        min_interval: float = 1.0,
        max_retries: int = 3,
        timeout: float = 30.0,
        obey_robots: bool = True,
        backoff_base: float = 1.0,
        session=None,
        sleep=time.sleep,
        monotonic=time.monotonic,
    ):
        self.user_agent = user_agent
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self.obey_robots = obey_robots
        self.backoff_base = backoff_base
        self._session = session if session is not None else requests.Session()
        self._sleep = sleep
        self._monotonic = monotonic
        self._last_request: dict[str, float] = {}
        self._lock = threading.Lock()
        self.robots = RobotsCache(self._session, user_agent)

    def _pace(self, url: str) -> None:
        """Block until enough time has passed since the last hit on this host."""
        host = urlsplit(url).netloc
        delay = self.min_interval
        if self.obey_robots:
            crawl_delay = self.robots.crawl_delay(url)
            if crawl_delay is not None:
                delay = max(delay, crawl_delay)

        with self._lock:
            last = self._last_request.get(host)
            now = self._monotonic()
            wait = 0.0 if last is None else delay - (now - last)
            # Reserve the slot before releasing the lock so concurrent callers
            # queue up behind each other instead of all sleeping the same wait.
            self._last_request[host] = now + max(wait, 0.0)
        if wait > 0:
            self._sleep(wait)

    def _retry_after(self, resp, attempt: int) -> float:
        header = resp.headers.get("Retry-After") if resp.headers else None
        if header:
            try:
                return max(float(header), 0.0)
            except ValueError:
                pass
        return self.backoff_base * (2**attempt)

    def get(self, url: str, **kwargs):
        """GET ``url``, honouring robots.txt, pacing and retries.

        Raises ``RobotsDisallowed`` when the host forbids the path.
        """
        if self.obey_robots and not self.robots.can_fetch(url):
            raise RobotsDisallowed(f"robots.txt disallows {url}")

        headers = {"User-Agent": self.user_agent}
        headers.update(kwargs.pop("headers", None) or {})
        kwargs.setdefault("timeout", self.timeout)

        last_exc = None
        for attempt in range(self.max_retries + 1):
            self._pace(url)
            try:
                resp = self._session.get(url, headers=headers, **kwargs)
            except requests.RequestException as exc:
                last_exc = exc
                if attempt >= self.max_retries:
                    raise
                self._sleep(self.backoff_base * (2**attempt))
                continue

            if resp.status_code in RETRY_STATUS and attempt < self.max_retries:
                self._sleep(self._retry_after(resp, attempt))
                continue
            return resp

        raise last_exc  # pragma: no cover - loop always returns or raises
