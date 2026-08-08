"""Tests for `pwb_toolbox.scraping`.

Nothing here touches the network. HTTP is served by `FakeHTTP`, and the
pacing/retry logic in `PoliteSession` runs against injected clock and sleep
functions so the tests stay fast.
"""

import base64
import json

import pytest
import requests

from pwb_toolbox.scraping import (
    GitHubSource,
    PoliteSession,
    RobotsDisallowed,
    ScriptRecord,
    ScriptStore,
    SkippedRepository,
    TermsNotAccepted,
    TradingViewSource,
    declaration,
    detect_language,
    extract_pine_source,
    input_names,
    is_probably_commercial,
    looks_like_pinescript,
    looks_like_thinkscript,
    pine_version,
    strip_comments,
)

PINE_STRATEGY = """//@version=5
strategy("Dual MA Cross", overlay=true, initial_capital=10000)
fast = input.int(10, title="Fast length")
slow = input.int(30, title="Slow length")
maFast = ta.sma(close, fast)
maSlow = ta.sma(close, slow)
if ta.crossover(maFast, maSlow)
    strategy.entry("long", strategy.long)
plot(maFast)
"""

THINKSCRIPT_STUDY = """# Simple momentum study
declare lower;
input length = 14;
def momentum = close - close[length];
plot Momentum = momentum;
AddLabel(yes, "Momentum: " + momentum);
"""

TYPESCRIPT_FILE = """import { Series } from "./series";

export function sma(values: number[], length: number): number[] {
  const out = [];
  return out;
}
"""


class FakeResponse:
    def __init__(self, status_code=200, text="", payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}
        self.text = text if payload is None else json.dumps(payload)

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON payload")
        return self._payload


class FakeHTTP:
    """A `requests.Session` stand-in backed by a URL -> response mapping."""

    def __init__(self, routes=None, default=None):
        self.routes = routes or {}
        self.default = default or FakeResponse(status_code=404)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        result = self.routes.get(url, self.default)
        if isinstance(result, list):
            # A queue: each call pops the next scripted response.
            return result.pop(0) if result else self.default
        if isinstance(result, Exception):
            raise result
        return result


class FakeClock:
    def __init__(self):
        self.now = 1000.0
        self.slept = []

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.slept.append(seconds)


def make_session(routes=None, default=None, **kwargs):
    http = FakeHTTP(routes, default)
    clock = FakeClock()
    kwargs.setdefault("min_interval", 0.0)
    session = PoliteSession(
        session=http, sleep=clock.sleep, monotonic=clock.monotonic, **kwargs
    )
    return session, http, clock


# --- languages ---------------------------------------------------------------


def test_pine_version_parsed():
    assert pine_version(PINE_STRATEGY) == 5
    assert pine_version("plot(close)") is None


def test_declaration_returns_kind_and_title():
    assert declaration(PINE_STRATEGY) == ("strategy", "Dual MA Cross")


def test_declaration_normalises_legacy_study_to_indicator():
    kind, title = declaration('//@version=4\nstudy("Legacy RSI", overlay=false)')
    assert (kind, title) == ("indicator", "Legacy RSI")


def test_declaration_prefers_title_keyword_over_positional():
    code = 'indicator("short", title="Full Name")'
    assert declaration(code) == ("indicator", "Full Name")


def test_declaration_none_when_absent():
    assert declaration("x = close\nplot(x)") is None


def test_strip_comments_keeps_double_slash_inside_string():
    code = 'label.new(bar_index, high, "https://example.com")  // trailing'
    assert strip_comments(code).rstrip() == (
        'label.new(bar_index, high, "https://example.com")'
    )


def test_declaration_ignores_commented_out_line():
    code = '//@version=5\n// strategy("Not This")\nindicator("Real One")'
    assert declaration(code) == ("indicator", "Real One")


def test_input_names_in_source_order_without_duplicates():
    assert input_names(PINE_STRATEGY) == ["fast", "slow"]


def test_looks_like_pinescript_accepts_and_rejects():
    assert looks_like_pinescript(PINE_STRATEGY)
    assert not looks_like_pinescript(TYPESCRIPT_FILE)
    assert not looks_like_pinescript("# just a comment\n")


def test_looks_like_thinkscript_accepts_study():
    assert looks_like_thinkscript(THINKSCRIPT_STUDY)


def test_looks_like_thinkscript_rejects_typescript():
    """The `.ts` extension is shared, so content has to break the tie."""
    assert not looks_like_thinkscript(TYPESCRIPT_FILE)


def test_pinescript_and_thinkscript_do_not_cross_match():
    assert not looks_like_thinkscript(PINE_STRATEGY)
    assert not looks_like_pinescript(THINKSCRIPT_STUDY)


@pytest.mark.parametrize(
    "header",
    [
        "// Premium members only - do not share",
        "# All Rights Reserved",
        "// Requires a valid license key",
    ],
)
def test_is_probably_commercial_flags_paid_headers(header):
    assert is_probably_commercial(header + "\n" + PINE_STRATEGY)


def test_is_probably_commercial_ignores_ordinary_scripts():
    assert not is_probably_commercial(PINE_STRATEGY)
    assert not is_probably_commercial(THINKSCRIPT_STUDY)


# --- polite session ----------------------------------------------------------


ROBOTS_URL = "https://example.com/robots.txt"


def test_robots_disallow_blocks_request():
    routes = {ROBOTS_URL: FakeResponse(text="User-agent: *\nDisallow: /private/")}
    session, _, _ = make_session(routes, obey_robots=True)
    with pytest.raises(RobotsDisallowed):
        session.get("https://example.com/private/thing")


def test_robots_allows_unlisted_path():
    routes = {
        ROBOTS_URL: FakeResponse(text="User-agent: *\nDisallow: /private/"),
        "https://example.com/public": FakeResponse(text="ok"),
    }
    session, _, _ = make_session(routes, obey_robots=True)
    assert session.get("https://example.com/public").text == "ok"


def test_missing_robots_txt_allows_everything():
    routes = {"https://example.com/x": FakeResponse(text="ok")}
    session, _, _ = make_session(routes, obey_robots=True)  # robots.txt 404s
    assert session.get("https://example.com/x").status_code == 200


def test_server_error_on_robots_txt_fails_closed():
    """An unreachable robots.txt is not permission to crawl."""
    routes = {ROBOTS_URL: FakeResponse(status_code=503)}
    session, _, _ = make_session(routes, obey_robots=True)
    with pytest.raises(RobotsDisallowed):
        session.get("https://example.com/anything")


def test_network_failure_on_robots_txt_fails_closed():
    routes = {ROBOTS_URL: requests.ConnectionError("boom")}
    session, _, _ = make_session(routes, obey_robots=True)
    with pytest.raises(RobotsDisallowed):
        session.get("https://example.com/anything")


def test_robots_txt_fetched_once_per_host():
    routes = {
        ROBOTS_URL: FakeResponse(text="User-agent: *\nAllow: /"),
        "https://example.com/a": FakeResponse(text="a"),
        "https://example.com/b": FakeResponse(text="b"),
    }
    session, http, _ = make_session(routes, obey_robots=True)
    session.get("https://example.com/a")
    session.get("https://example.com/b")
    assert http.calls.count(ROBOTS_URL) == 1


def test_requests_to_same_host_are_spaced_by_min_interval():
    routes = {"https://example.com/x": FakeResponse(text="ok")}
    session, _, clock = make_session(routes, obey_robots=False, min_interval=2.0)
    session.get("https://example.com/x")
    assert clock.slept == []
    session.get("https://example.com/x")
    assert clock.slept == [2.0]


def test_crawl_delay_overrides_a_shorter_min_interval():
    routes = {
        ROBOTS_URL: FakeResponse(text="User-agent: *\nCrawl-delay: 9"),
        "https://example.com/x": FakeResponse(text="ok"),
    }
    session, _, clock = make_session(routes, obey_robots=True, min_interval=1.0)
    session.get("https://example.com/x")
    session.get("https://example.com/x")
    assert clock.slept == [9.0]


def test_retries_on_429_and_honours_retry_after():
    routes = {
        "https://example.com/x": [
            FakeResponse(status_code=429, headers={"Retry-After": "3"}),
            FakeResponse(status_code=200, text="ok"),
        ]
    }
    session, _, clock = make_session(routes, obey_robots=False)
    resp = session.get("https://example.com/x")
    assert resp.status_code == 200
    assert clock.slept == [3.0]


def test_retries_use_exponential_backoff_without_retry_after():
    routes = {
        "https://example.com/x": [
            FakeResponse(status_code=500),
            FakeResponse(status_code=500),
            FakeResponse(status_code=200, text="ok"),
        ]
    }
    session, _, clock = make_session(routes, obey_robots=False, backoff_base=1.0)
    assert session.get("https://example.com/x").status_code == 200
    assert clock.slept == [1.0, 2.0]


def test_gives_up_and_returns_last_error_response():
    routes = {"https://example.com/x": FakeResponse(status_code=503)}
    session, _, _ = make_session(routes, obey_robots=False, max_retries=2)
    assert session.get("https://example.com/x").status_code == 503


# --- store -------------------------------------------------------------------


def _record(code=PINE_STRATEGY, **kwargs):
    defaults = dict(
        source="github",
        url="https://github.com/o/r/blob/main/a.pine",
        language="pinescript",
        title="Dual MA Cross",
        code=code,
    )
    defaults.update(kwargs)
    return ScriptRecord(**defaults)


def test_store_writes_code_and_manifest(tmp_path):
    store = ScriptStore(tmp_path)
    assert store.add(_record()) is True
    assert len(store) == 1

    entries = store.entries()
    assert len(entries) == 1
    assert entries[0]["title"] == "Dual MA Cross"
    assert "code" not in entries[0]
    assert (tmp_path / entries[0]["path"]).read_text() == PINE_STRATEGY


def test_store_deduplicates_identical_code(tmp_path):
    store = ScriptStore(tmp_path)
    store.add(_record())
    assert store.add(_record(url="https://github.com/other/repo/blob/main/b.pine")) is (
        False
    )
    assert len(store) == 1
    assert len(store.entries()) == 1


def test_store_dedup_survives_reopening(tmp_path):
    ScriptStore(tmp_path).add(_record())
    reopened = ScriptStore(tmp_path)
    assert len(reopened) == 1
    assert reopened.add(_record()) is False


def test_store_roundtrips_records(tmp_path):
    store = ScriptStore(tmp_path)
    store.add(_record(pine_version=5, kind="strategy", license="MIT"))
    (restored,) = store.records()
    assert restored.code == PINE_STRATEGY
    assert restored.license == "MIT"
    assert restored.pine_version == 5


def test_store_uses_language_specific_extension(tmp_path):
    store = ScriptStore(tmp_path)
    store.add(_record(code=THINKSCRIPT_STUDY, language="thinkscript"))
    assert store.entries()[0]["path"].endswith(".ts")


def test_extend_counts_only_new_records(tmp_path):
    store = ScriptStore(tmp_path)
    records = [_record(), _record(), _record(code=THINKSCRIPT_STUDY)]
    assert store.extend(records) == 2


# --- github source -----------------------------------------------------------


def test_detect_language_uses_content_not_extension():
    assert detect_language("a.ts", THINKSCRIPT_STUDY) == "thinkscript"
    assert detect_language("a.ts", TYPESCRIPT_FILE) is None
    assert detect_language("a.pine", PINE_STRATEGY) == "pinescript"
    assert detect_language("notes.md", PINE_STRATEGY) is None


def _github_routes(files, license_id="MIT", default_branch="main"):
    """Build API routes for a repo containing ``{path: code}``."""
    repo = "octo/pine"
    tree = []
    routes = {
        f"https://api.github.com/repos/{repo}": FakeResponse(
            payload={
                "default_branch": default_branch,
                "license": {"spdx_id": license_id} if license_id else None,
            }
        )
    }
    for index, (path, code) in enumerate(files.items()):
        sha = f"sha{index}"
        encoded = base64.b64encode(code.encode()).decode()
        tree.append({"path": path, "type": "blob", "sha": sha, "size": len(code)})
        routes[f"https://api.github.com/repos/{repo}/git/blobs/{sha}"] = FakeResponse(
            payload={"content": encoded, "encoding": "base64"}
        )
    routes[f"https://api.github.com/repos/{repo}/git/trees/{default_branch}"] = (
        FakeResponse(payload={"tree": tree, "truncated": False})
    )
    return repo, routes


def _github_source(routes, **kwargs):
    session, _, _ = make_session(routes, obey_robots=False)
    return GitHubSource(session=session, token=None, **kwargs)


def test_github_collect_yields_parsed_records():
    repo, routes = _github_routes({"strategies/ma.pine": PINE_STRATEGY})
    (record,) = list(_github_source(routes).collect(repo))

    assert record.source == "github"
    assert record.language == "pinescript"
    assert record.title == "Dual MA Cross"
    assert record.kind == "strategy"
    assert record.pine_version == 5
    assert record.license == "MIT"
    assert record.author == "octo"
    assert record.url == "https://github.com/octo/pine/blob/main/strategies/ma.pine"


def test_github_collect_skips_non_script_files():
    repo, routes = _github_routes(
        {
            "a.pine": PINE_STRATEGY,
            "src/index.ts": TYPESCRIPT_FILE,
            "study.ts": THINKSCRIPT_STUDY,
        }
    )
    records = list(_github_source(routes).collect(repo))
    assert sorted(r.language for r in records) == ["pinescript", "thinkscript"]


def test_github_rejects_repository_without_permissive_license():
    repo, routes = _github_routes({"a.pine": PINE_STRATEGY}, license_id="NOASSERTION")
    with pytest.raises(SkippedRepository):
        list(_github_source(routes).collect(repo))


def test_github_collects_unlicensed_repo_when_explicitly_allowed():
    repo, routes = _github_routes({"a.pine": PINE_STRATEGY}, license_id=None)
    records = list(_github_source(routes, require_license=False).collect(repo))
    assert len(records) == 1
    assert records[0].license is None


def test_github_skips_files_marked_commercial():
    repo, routes = _github_routes(
        {
            "free.pine": PINE_STRATEGY,
            "paid.pine": "// Premium members only\n" + PINE_STRATEGY,
        }
    )
    source = _github_source(routes)
    records = list(source.collect(repo))
    assert [r.extra["path"] for r in records] == ["free.pine"]
    assert any("commercial" in w for w in source.warnings)


def test_github_honours_include_commercial_override():
    repo, routes = _github_routes(
        {"paid.pine": "// Premium members only\n" + PINE_STRATEGY}
    )
    records = list(_github_source(routes, skip_commercial=False).collect(repo))
    assert len(records) == 1


def test_github_skips_files_over_size_limit():
    repo, routes = _github_routes({"a.pine": PINE_STRATEGY})
    assert list(_github_source(routes, max_bytes=10).collect(repo)) == []


def test_github_warns_when_tree_listing_truncated():
    repo, routes = _github_routes({"a.pine": PINE_STRATEGY})
    routes["https://api.github.com/repos/octo/pine/git/trees/main"] = FakeResponse(
        payload={"tree": [], "truncated": True}
    )
    source = _github_source(routes)
    list(source.collect(repo))
    assert any("truncated" in w for w in source.warnings)


# --- tradingview source ------------------------------------------------------


def test_tradingview_refuses_without_accepting_terms():
    session, _, _ = make_session({}, obey_robots=False)
    source = TradingViewSource(session=session)
    with pytest.raises(TermsNotAccepted):
        source.fetch("https://www.tradingview.com/script/abc123-Test/")


def test_tradingview_rejects_non_script_urls():
    session, _, _ = make_session({}, obey_robots=False)
    source = TradingViewSource(session=session, accept_terms=True)
    with pytest.raises(ValueError):
        source.fetch("https://www.tradingview.com/chart/abc/")


def test_extract_pine_source_from_embedded_json():
    html = (
        "<html><body><script>"
        + json.dumps({"source": PINE_STRATEGY, "id": 7})
        + "</script></body></html>"
    )
    assert extract_pine_source(html) == PINE_STRATEGY


def test_extract_pine_source_from_rendered_code_block():
    html = f"<html><body><pre>{PINE_STRATEGY}</pre></body></html>"
    extracted = extract_pine_source(html)
    assert extracted is not None
    assert "strategy.entry" in extracted


def test_extract_pine_source_returns_none_when_value_is_not_pinescript():
    """A wrong selector must yield nothing rather than plausible garbage."""
    html = "<html><script>" + json.dumps({"source": "web"}) + "</script></html>"
    assert extract_pine_source(html) is None


def test_extract_pine_source_returns_none_on_empty_page():
    assert extract_pine_source("<html><body>No script here</body></html>") is None


def test_tradingview_fetch_builds_record():
    url = "https://www.tradingview.com/script/abc123-Dual-MA/"
    html = (
        "<html><head><title>Dual MA</title></head><body><script>"
        + json.dumps({"source": PINE_STRATEGY})
        + "</script></body></html>"
    )
    session, _, _ = make_session({url: FakeResponse(text=html)}, obey_robots=False)
    record = TradingViewSource(session=session, accept_terms=True).fetch(url)

    assert record is not None
    assert record.source == "tradingview"
    assert record.title == "Dual MA Cross"
    assert record.kind == "strategy"
    assert record.license is None


def test_tradingview_fetch_returns_none_for_protected_script():
    url = "https://www.tradingview.com/script/abc123-Protected/"
    html = "<html><body>This script is invite-only.</body></html>"
    session, _, _ = make_session({url: FakeResponse(text=html)}, obey_robots=False)
    assert TradingViewSource(session=session, accept_terms=True).fetch(url) is None


def test_tradingview_respects_robots_disallow():
    url = "https://www.tradingview.com/script/abc123-Test/"
    routes = {
        "https://www.tradingview.com/robots.txt": FakeResponse(
            text="User-agent: *\nDisallow: /script/"
        )
    }
    session, _, _ = make_session(routes, obey_robots=True)
    source = TradingViewSource(session=session, accept_terms=True)
    with pytest.raises(RobotsDisallowed):
        source.fetch(url)
