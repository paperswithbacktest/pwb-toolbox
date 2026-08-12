"""Tests for the Grok chat exporter.

Everything here runs offline: the HTTP layer is exercised against a fake
``requests.Session`` and the dump readers against fixtures built in ``tmp_path``.
"""

import json
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.grok_export import (
    auth,
    client as client_module,
    merge,
    official,
    render,
    schema,
)
from tools.grok_export.cli import main
from tools.grok_export.client import GrokClient, SessionExpired

# --------------------------------------------------------------------------
# fake transport
# --------------------------------------------------------------------------


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {"content-type": "application/json"}
        if text is not None:
            self.text = text
        else:
            self.text = json.dumps(payload) if payload is not None else ""

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


class FakeSession:
    def __init__(self, handler):
        self.headers = {}
        self._handler = handler
        self.calls = []

    def request(self, method, url, timeout=None, **kwargs):
        self.calls.append((method, url, kwargs))
        return self._handler(method, url, kwargs)


def make_client(handler, **kwargs):
    """A GrokClient wired to ``handler``, with throttling and retries off."""
    kwargs.setdefault("delay", 0)
    kwargs.setdefault("max_retries", 0)
    return GrokClient("sso=abc; sso-rw=def", session=FakeSession(handler), **kwargs)


# --------------------------------------------------------------------------
# schema
# --------------------------------------------------------------------------


def test_pick_skips_empty_values():
    assert schema.pick({"a": "", "b": None, "c": "x"}, ("a", "b", "c")) == "x"
    assert schema.pick({}, ("a",), default="fallback") == "fallback"
    assert schema.pick("not a dict", ("a",)) is None


@pytest.mark.parametrize(
    "value,expected",
    [
        ("2026-08-08T12:30:00Z", datetime(2026, 8, 8, 12, 30, tzinfo=timezone.utc)),
        (
            "2026-08-08T12:30:00+00:00",
            datetime(2026, 8, 8, 12, 30, tzinfo=timezone.utc),
        ),
        (1754656200, datetime(2025, 8, 8, 12, 30, tzinfo=timezone.utc)),
        (1754656200000, datetime(2025, 8, 8, 12, 30, tzinfo=timezone.utc)),
        ("1754656200", datetime(2025, 8, 8, 12, 30, tzinfo=timezone.utc)),
    ],
)
def test_to_datetime_accepts_iso_and_epoch_forms(value, expected):
    assert schema.to_datetime(value) == expected


def test_to_datetime_handles_nanosecond_precision():
    """Python 3.10's fromisoformat rejects more than six fractional digits."""
    parsed = schema.to_datetime("2026-08-08T12:30:00.123456789Z")
    assert parsed == datetime(2026, 8, 8, 12, 30, 0, 123456, tzinfo=timezone.utc)


def test_to_datetime_returns_none_for_junk():
    for value in (None, "", "not a date", True, {}):
        assert schema.to_datetime(value) is None


def test_naive_timestamps_are_assumed_utc():
    assert schema.to_datetime("2026-08-08T12:30:00").tzinfo is timezone.utc


@pytest.mark.parametrize(
    "payload,expected",
    [
        ({"isUser": True}, "user"),
        ({"isUser": False}, "assistant"),
        ({"sender": "human"}, "user"),
        ({"role": "ASSISTANT"}, "assistant"),
        ({"sender": "grok"}, "assistant"),
        ({"role": {"name": "user"}}, "user"),
        ({}, "unknown"),
        ({"role": "moderator"}, "unknown"),
    ],
)
def test_normalize_role(payload, expected):
    assert schema.normalize_role(payload) == expected


def test_role_prefers_user_token_in_compound_value():
    """RESPONSE_TYPE_HUMAN contains both an assistant and a user token."""
    assert schema.normalize_role({"responseType": "RESPONSE_TYPE_HUMAN"}) == "user"
    assert (
        schema.normalize_role({"responseType": "RESPONSE_TYPE_ASSISTANT"})
        == "assistant"
    )


def test_extract_text_descends_nested_shapes():
    assert schema.extract_text({"message": "hello"}) == "hello"
    assert schema.extract_text({"content": {"text": "nested"}}) == "nested"
    assert schema.extract_text({"content": [{"text": "a"}, {"text": "b"}]}) == "a\n\nb"
    assert schema.extract_text({"unrelated": 1}) == ""


def test_extract_text_stops_recursing_on_deep_nesting():
    payload = current = {}
    for _ in range(20):
        nested = {}
        current["content"] = nested
        current = nested
    current["text"] = "deep"
    assert schema.extract_text(payload) == ""


def test_parse_conversation_merges_listing_and_detail():
    listing = {
        "conversationId": "abc-123",
        "title": "Backtesting",
        "createTime": 1754656200,
    }
    detail = {
        "responses": [
            {"sender": "human", "message": "hi", "createTime": 2},
            {"sender": "grok", "message": "hello", "createTime": 1},
        ]
    }
    conversation = schema.parse_conversation(listing, detail)

    assert conversation.id == "abc-123"
    assert conversation.title == "Backtesting"
    assert [m.role for m in conversation.messages] == ["assistant", "user"]
    assert conversation.raw == {"listing": listing, "detail": detail}


def test_parse_conversation_unwraps_nested_entry():
    entry = {"conversation": {"id": "x1", "title": "Wrapped"}, "messages": []}
    conversation = schema.parse_conversation(entry)
    assert (conversation.id, conversation.title) == ("x1", "Wrapped")


def test_parse_conversation_keeps_order_when_timestamps_missing():
    detail = {
        "responses": [
            {"sender": "human", "message": "first"},
            {"sender": "grok", "message": "second"},
        ]
    }
    messages = schema.parse_conversation({"id": "a"}, detail).messages
    assert [m.text for m in messages] == ["first", "second"]


def test_display_title_falls_back_to_id():
    assert schema.Conversation(id="abcdef1234").display_title == "Untitled abcdef12"
    assert schema.Conversation(id="").display_title == "Untitled"


def test_next_cursor_reads_nested_pagination():
    assert schema.next_cursor({"nextPageToken": "t1"}) == "t1"
    assert schema.next_cursor({"pagination": {"cursor": "t2"}}) == "t2"
    assert schema.next_cursor({"conversations": []}) is None


# --------------------------------------------------------------------------
# auth
# --------------------------------------------------------------------------


def test_parse_cookie_header_from_curl_command():
    command = (
        "curl 'https://grok.com/rest/app-chat/conversations' "
        "-H 'accept: application/json' "
        "-H 'cookie: sso=abc; sso-rw=def' "
        "--compressed"
    )
    assert auth.parse_cookie_header(command) == "sso=abc; sso-rw=def"


def test_parse_cookie_header_from_curl_b_flag():
    assert auth.parse_cookie_header("curl https://grok.com -b 'sso=abc'") == "sso=abc"


def test_parse_cookie_header_from_bare_header_and_string():
    assert auth.parse_cookie_header("cookie: sso=abc; x=1") == "sso=abc; x=1"
    assert auth.parse_cookie_header("sso=abc; x=1") == "sso=abc; x=1"
    assert auth.parse_cookie_header("") == ""


def test_parse_cookie_header_collapses_multiline_curl():
    command = "curl 'https://grok.com' \\\n  -H 'cookie: sso=abc;\n  sso-rw=def' \\\n"
    assert auth.parse_cookie_header(command) == "sso=abc; sso-rw=def"


def test_cookie_names_never_leaks_values():
    names = auth.cookie_names("sso=secret-value; sso-rw=other")
    assert names == ["sso", "sso-rw"]
    assert "secret-value" not in "".join(names)


def test_missing_cookies_reports_absent_session_keys():
    assert auth.missing_cookies("sso=a; sso-rw=b") == []
    assert auth.missing_cookies("other=1") == ["sso", "sso-rw"]


def test_load_cookie_reads_file_then_env(tmp_path, monkeypatch):
    path = tmp_path / "curl.txt"
    path.write_text("curl 'https://grok.com' -H 'cookie: sso=from-file'")
    assert auth.load_cookie(path) == "sso=from-file"

    monkeypatch.setenv(auth.ENV_VAR, "sso=from-env")
    assert auth.load_cookie(None) == "sso=from-env"


def test_load_cookie_accepts_a_literal_string(monkeypatch):
    monkeypatch.delenv(auth.ENV_VAR, raising=False)
    assert auth.load_cookie("sso=literal; sso-rw=x") == "sso=literal; sso-rw=x"


def test_load_cookie_without_any_source_explains_how_to_get_one(monkeypatch):
    monkeypatch.delenv(auth.ENV_VAR, raising=False)
    with pytest.raises(auth.AuthError, match="Copy as cURL"):
        auth.load_cookie(None)


# --------------------------------------------------------------------------
# client
# --------------------------------------------------------------------------


def test_client_sends_cookie_and_browser_headers():
    grok = make_client(lambda *a: FakeResponse(payload={"conversations": []}))
    assert grok.session.headers["cookie"] == "sso=abc; sso-rw=def"
    assert grok.session.headers["referer"] == "https://grok.com/"


def test_list_conversations_follows_the_cursor():
    pages = {
        None: {"conversations": [{"id": "a"}], "nextPageToken": "p2"},
        "p2": {"conversations": [{"id": "b"}]},
    }

    def handler(method, url, kwargs):
        return FakeResponse(payload=pages[kwargs["params"].get("cursor")])

    grok = make_client(handler)
    assert [c["id"] for c in grok.list_conversations()] == ["a", "b"]


def test_list_conversations_stops_when_a_page_repeats_itself():
    """An endpoint that ignores the cursor must not loop forever."""
    page = {"conversations": [{"id": "a"}], "nextPageToken": "always"}
    grok = make_client(lambda *a: FakeResponse(payload=page))
    assert [c["id"] for c in grok.list_conversations()] == ["a"]


def test_list_conversations_honours_limit():
    page = {"conversations": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}
    grok = make_client(lambda *a: FakeResponse(payload=page))
    assert len(list(grok.list_conversations(limit=2))) == 2


def test_client_falls_through_to_the_next_candidate_path():
    def handler(method, url, kwargs):
        if url.endswith("/rest/app-chat/conversations"):
            return FakeResponse(status_code=404, payload={})
        return FakeResponse(payload={"conversations": [{"id": "a"}]})

    grok = make_client(handler)
    assert list(grok.list_conversations()) == [{"id": "a"}]
    assert grok._resolved["list"] == client_module.LIST_PATHS[1]


def test_resolved_path_is_reused_on_later_calls():
    def handler(method, url, kwargs):
        if url.endswith("/rest/app-chat/conversations"):
            return FakeResponse(status_code=404, payload={})
        return FakeResponse(payload={"conversations": []})

    grok = make_client(handler)
    grok.list_page()
    before = len(grok.session.calls)
    grok.list_page()
    # One call, not two: the dead first candidate is not retried.
    assert len(grok.session.calls) - before == 1


def test_unauthorised_response_raises_session_expired():
    grok = make_client(lambda *a: FakeResponse(status_code=401, payload={}))
    with pytest.raises(SessionExpired, match="rejected the session cookie"):
        grok.list_page()


def test_html_login_page_is_reported_as_an_expired_session():
    response = FakeResponse(
        text="<html><body>Sign in</body></html>",
        headers={"content-type": "text/html"},
    )
    grok = make_client(lambda *a: response)
    with pytest.raises(SessionExpired, match="expired"):
        grok.list_page()


def test_all_candidate_paths_404_raises_endpoint_not_found():
    grok = make_client(lambda *a: FakeResponse(status_code=404, payload={}))
    with pytest.raises(client_module.EndpointNotFound, match="--list-path"):
        grok.list_page()


def test_retries_then_succeeds_on_transient_failure(monkeypatch):
    monkeypatch.setattr(client_module.time, "sleep", lambda _: None)
    attempts = []

    def handler(method, url, kwargs):
        attempts.append(url)
        if len(attempts) == 1:
            return FakeResponse(status_code=503, payload={})
        return FakeResponse(payload={"conversations": [{"id": "a"}]})

    grok = make_client(handler, max_retries=2)
    assert list(grok.list_conversations()) == [{"id": "a"}]
    assert len(attempts) == 2


def test_retry_after_header_caps_the_wait():
    response = FakeResponse(status_code=429, headers={"retry-after": "999"})
    assert GrokClient._retry_after(response, 0) == 60.0
    assert GrokClient._retry_after(FakeResponse(status_code=429), 3) == 8.0


def test_fetch_detail_interpolates_the_conversation_id():
    seen = []

    def handler(method, url, kwargs):
        seen.append(url)
        return FakeResponse(payload={"responses": []})

    make_client(handler).fetch_detail("abc-123")
    assert seen[0].endswith("/rest/app-chat/conversations/abc-123/response-node")


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------


def test_slugify_is_filesystem_safe():
    assert render.slugify("Hello, World! / Grok?") == "hello-world-grok"
    assert render.slugify("") == ""
    assert len(render.slugify("x" * 200)) <= 60


def test_conversation_stem_combines_date_title_and_id():
    conversation = schema.Conversation(
        id="abcdef12-3456",
        title="My Chat",
        created=datetime(2026, 8, 8, tzinfo=timezone.utc),
    )
    assert render.conversation_stem(conversation) == "2026-08-08-my-chat-abcdef12"


def test_conversation_stem_survives_missing_metadata():
    assert render.conversation_stem(schema.Conversation(id="")) == "conversation"


def test_render_markdown_emits_parseable_frontmatter():
    conversation = schema.Conversation(
        id="abc",
        title='Quotes: "risky" \\ backslash',
        created=datetime(2026, 8, 8, tzinfo=timezone.utc),
        messages=[
            schema.Message(role="user", text="What is a Sharpe ratio?"),
            schema.Message(role="assistant", text="A risk-adjusted return measure."),
        ],
    )
    text = render.render_markdown(conversation)

    assert text.startswith("---\n")
    title_line = next(l for l in text.splitlines() if l.startswith("title:"))
    # The title is JSON-quoted, which is valid YAML and survives round-tripping.
    assert json.loads(title_line.split(": ", 1)[1]) == 'Quotes: "risky" \\ backslash'
    assert "## You" in text and "## Grok" in text
    assert "What is a Sharpe ratio?" in text


def test_render_markdown_notes_an_empty_conversation():
    text = render.render_markdown(schema.Conversation(id="a", title="Empty"))
    assert "_No messages were returned" in text


def test_write_markdown_does_not_overwrite_a_collision(tmp_path):
    conversation = schema.Conversation(id="abc", title="Same")
    first = render.write_markdown(tmp_path, conversation)
    second = render.write_markdown(tmp_path, conversation)
    assert first != second
    assert first.exists() and second.exists()


def test_write_raw_round_trips(tmp_path):
    path = render.write_raw(tmp_path, "abc-123", {"listing": {"id": "abc-123"}})
    assert path == render.raw_path(tmp_path, "abc-123")
    assert json.loads(path.read_text())["listing"]["id"] == "abc-123"


def test_write_index_lists_every_conversation(tmp_path):
    conversations = [
        schema.Conversation(
            id="a", title="One", messages=[schema.Message("user", "hi")]
        ),
        schema.Conversation(id="b", title="Two"),
    ]
    entries = json.loads(render.write_index(tmp_path, conversations).read_text())
    assert [e["id"] for e in entries] == ["a", "b"]
    assert entries[0]["messages"] == 1


# --------------------------------------------------------------------------
# official export
# --------------------------------------------------------------------------


DUMP = {
    "account": {"email": "someone@example.com"},
    "chats": [
        {
            "id": "conv-1",
            "title": "First chat",
            "createTime": "2026-01-02T03:04:05Z",
            "messages": [
                {"role": "user", "text": "hello"},
                {"role": "assistant", "text": "hi there"},
            ],
        },
        {
            "id": "conv-2",
            "title": "Second chat",
            "messages": [{"role": "user", "text": "another"}],
        },
    ],
}


def test_walk_conversations_finds_nested_chats():
    found = list(official.walk_conversations(DUMP))
    assert [c["id"] for c in found] == ["conv-1", "conv-2"]


def test_walk_conversations_ignores_metadata_only_lists():
    payload = {"settings": {"items": [{"key": "theme", "value": "dark"}]}}
    assert list(official.walk_conversations(payload)) == []


def test_load_conversations_from_json_file(tmp_path):
    path = tmp_path / "dump.json"
    path.write_text(json.dumps(DUMP), encoding="utf-8")

    conversations = official.load_conversations(path)
    assert [c.id for c in conversations] == ["conv-1", "conv-2"]
    assert [m.role for m in conversations[0].messages] == ["user", "assistant"]


def test_load_conversations_from_zip_archive(tmp_path):
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("data/chats.json", json.dumps(DUMP))
        handle.writestr("README.txt", "not json")

    assert [c.id for c in official.load_conversations(archive)] == ["conv-1", "conv-2"]


def test_load_conversations_from_directory_and_jsonl(tmp_path):
    source = tmp_path / "dump"
    source.mkdir()
    (source / "chats.jsonl").write_text(
        "\n".join(json.dumps(chat) for chat in DUMP["chats"]), encoding="utf-8"
    )
    assert [c.id for c in official.load_conversations(source)] == ["conv-1", "conv-2"]


def test_load_conversations_deduplicates_repeated_ids(tmp_path):
    path = tmp_path / "dump.json"
    path.write_text(
        json.dumps({"a": DUMP["chats"], "b": DUMP["chats"]}), encoding="utf-8"
    )
    assert len(official.load_conversations(path)) == 2


def test_undated_conversations_sort_last_without_comparing_none(tmp_path):
    """Two undated conversations must not trip a None < None comparison."""
    payload = {
        "chats": [
            {
                "id": "x",
                "title": "No date",
                "messages": [{"role": "user", "text": "a"}],
            },
            {
                "id": "y",
                "title": "Also none",
                "messages": [{"role": "user", "text": "b"}],
            },
            {
                "id": "z",
                "title": "Dated",
                "createTime": "2020-01-01T00:00:00Z",
                "messages": [{"role": "user", "text": "c"}],
            },
        ]
    }
    path = tmp_path / "dump.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert [c.id for c in official.load_conversations(path)] == ["z", "x", "y"]


# --------------------------------------------------------------------------
# cli
# --------------------------------------------------------------------------


def test_convert_writes_markdown_and_index(tmp_path):
    source = tmp_path / "dump.json"
    source.write_text(json.dumps(DUMP), encoding="utf-8")
    out = tmp_path / "out"

    assert main(["convert", str(source), "--out", str(out)]) == 0

    markdown = sorted(p.name for p in (out / "markdown").glob("*.md"))
    assert len(markdown) == 2
    assert (out / "index.json").exists()
    assert "hi there" in (out / "markdown" / markdown[0]).read_text()


def test_convert_reports_an_unrecognised_dump(tmp_path, capsys):
    source = tmp_path / "dump.json"
    source.write_text(json.dumps({"unrelated": [1, 2, 3]}), encoding="utf-8")

    assert main(["convert", str(source), "--out", str(tmp_path / "out")]) == 1
    assert "No conversations recognised" in capsys.readouterr().err


def test_convert_on_a_missing_path_fails_cleanly(tmp_path, capsys):
    assert main(["convert", str(tmp_path / "nope.json")]) == 1
    assert "does not exist" in capsys.readouterr().err


def test_no_markdown_flag_writes_json_only(tmp_path):
    source = tmp_path / "dump.json"
    source.write_text(json.dumps(DUMP), encoding="utf-8")
    out = tmp_path / "out"

    assert main(["convert", str(source), "--out", str(out), "--no-markdown"]) == 0
    assert not (out / "markdown").exists()
    assert (out / "index.json").exists()


def test_render_rebuilds_markdown_from_raw_payloads(tmp_path):
    out = tmp_path / "out"
    render.write_raw(
        out / "raw",
        "conv-1",
        {
            "listing": {"id": "conv-1", "title": "Cached"},
            "detail": {"messages": [{"role": "user", "text": "from cache"}]},
        },
    )

    assert main(["render", "--out", str(out)]) == 0
    written = list((out / "markdown").glob("*.md"))
    assert len(written) == 1
    assert "from cache" in written[0].read_text()


def test_render_without_a_previous_pull_fails_cleanly(tmp_path, capsys):
    assert main(["render", "--out", str(tmp_path / "missing")]) == 1
    assert "Run `pull` first" in capsys.readouterr().err


def test_pull_writes_raw_markdown_and_index(tmp_path, monkeypatch):
    listing = {"conversations": [{"id": "conv-1", "title": "Sharpe"}]}
    detail = {"responses": [{"sender": "human", "message": "define sharpe"}]}

    def handler(method, url, kwargs):
        payload = detail if "conv-1" in url else listing
        return FakeResponse(payload=payload)

    monkeypatch.setattr(
        client_module.GrokClient,
        "__init__",
        _patched_init(handler),
    )
    monkeypatch.setenv(auth.ENV_VAR, "sso=a; sso-rw=b")

    out = tmp_path / "out"
    assert main(["pull", "--out", str(out), "--delay", "0"]) == 0

    assert (out / "raw" / "conv-1.json").exists()
    markdown = list((out / "markdown").glob("*.md"))
    assert len(markdown) == 1
    assert "define sharpe" in markdown[0].read_text()


def test_pull_skips_conversations_already_archived(tmp_path, monkeypatch):
    listing = {"conversations": [{"id": "conv-1", "title": "Cached"}]}
    detail_calls = []

    def handler(method, url, kwargs):
        if "conv-1" in url:
            detail_calls.append(url)
            return FakeResponse(payload={"responses": []})
        return FakeResponse(payload=listing)

    monkeypatch.setattr(client_module.GrokClient, "__init__", _patched_init(handler))
    monkeypatch.setenv(auth.ENV_VAR, "sso=a; sso-rw=b")

    out = tmp_path / "out"
    render.write_raw(
        out / "raw",
        "conv-1",
        {"listing": {"id": "conv-1", "title": "Cached"}, "detail": {"messages": []}},
    )

    assert main(["pull", "--out", str(out), "--delay", "0"]) == 0
    assert detail_calls == []


def test_pull_keeps_going_when_one_detail_fetch_fails(tmp_path, monkeypatch, capsys):
    listing = {"conversations": [{"id": "good"}, {"id": "bad"}]}

    def handler(method, url, kwargs):
        if "bad" in url:
            return FakeResponse(status_code=500, payload={})
        if "good" in url:
            return FakeResponse(payload={"responses": [{"role": "user", "text": "ok"}]})
        return FakeResponse(payload=listing)

    monkeypatch.setattr(client_module.GrokClient, "__init__", _patched_init(handler))
    monkeypatch.setenv(auth.ENV_VAR, "sso=a; sso-rw=b")

    out = tmp_path / "out"
    assert main(["pull", "--out", str(out), "--delay", "0"]) == 0

    entries = json.loads((out / "index.json").read_text())
    assert {e["id"] for e in entries} == {"good", "bad"}
    assert "warning" in capsys.readouterr().err


def test_pull_reports_an_expired_session(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        client_module.GrokClient,
        "__init__",
        _patched_init(lambda *a: FakeResponse(status_code=403, payload={})),
    )
    monkeypatch.setenv(auth.ENV_VAR, "sso=a; sso-rw=b")

    assert main(["pull", "--out", str(tmp_path / "out"), "--delay", "0"]) == 1
    assert "rejected the session cookie" in capsys.readouterr().err


def test_pull_without_a_cookie_exits_with_guidance(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(auth.ENV_VAR, raising=False)
    assert main(["pull", "--out", str(tmp_path / "out")]) == 2
    assert "Copy as cURL" in capsys.readouterr().err


def test_pull_warns_when_session_cookies_are_absent(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        client_module.GrokClient,
        "__init__",
        _patched_init(lambda *a: FakeResponse(payload={"conversations": []})),
    )
    monkeypatch.setenv(auth.ENV_VAR, "unrelated=1")

    main(["pull", "--out", str(tmp_path / "out"), "--delay", "0"])
    assert "session cookies sso, sso-rw are missing" in capsys.readouterr().err


def _patched_init(handler):
    """A GrokClient.__init__ replacement that swaps in a fake session."""
    original = client_module.GrokClient.__init__

    def patched(self, cookie, **kwargs):
        kwargs["session"] = FakeSession(handler)
        kwargs["delay"] = 0
        kwargs["max_retries"] = 0
        original(self, cookie, **kwargs)

    return patched


# --------------------------------------------------------------------------
# the real xAI export layout
#
# Shapes below mirror an actual accounts.x.ai download (content is synthetic):
# conversations wrap their metadata under "conversation", each turn wraps under
# "response", and turn timestamps are MongoDB extended JSON.
# --------------------------------------------------------------------------


XAI_EXPORT = {
    "conversations": [
        {
            "conversation": {
                "id": "90804d85-4de3-477f-8598-77e008cd89c3",
                "title": "EMA and RSI indicators",
                "create_time": "2026-07-28T00:29:26.009215Z",
                "modify_time": "2026-07-28T00:35:07.824Z",
                "starred": False,
            },
            "responses": [
                {
                    "response": {
                        "_id": "r1",
                        "message": "How do I combine EMA with RSI?",
                        "sender": "human",
                        "create_time": {"$date": {"$numberLong": "1785198572458"}},
                    },
                    "share_link": "",
                },
                {
                    "response": {
                        "_id": "r2",
                        "message": "Use the EMA for trend and RSI for timing.",
                        "sender": "ASSISTANT",
                        "create_time": {"$date": {"$numberLong": "1785198600000"}},
                    },
                    "share_link": "",
                },
            ],
        }
    ],
    "projects": [],
    "tasks": [],
    "media_posts": [],
}


def test_mongo_extended_json_timestamps_are_parsed():
    parsed = schema.to_datetime({"$date": {"$numberLong": "1785198572458"}})
    assert parsed == datetime(2026, 7, 28, 0, 29, 32, 458000, tzinfo=timezone.utc)


def test_protobuf_style_timestamps_are_parsed():
    assert schema.to_datetime({"seconds": 1754656200}) == datetime(
        2025, 8, 8, 12, 30, tzinfo=timezone.utc
    )


def test_unrecognised_timestamp_dict_is_none():
    assert schema.to_datetime({"unrelated": 1}) is None


def test_unwrap_turn_reaches_the_nested_response():
    turn = {"response": {"sender": "human", "message": "hi"}, "share_link": ""}
    assert schema.unwrap_turn(turn) == {"sender": "human", "message": "hi"}


def test_unwrap_turn_leaves_a_flat_turn_alone():
    turn = {"sender": "human", "message": "hi"}
    assert schema.unwrap_turn(turn) is turn


def test_parse_message_keeps_the_wrapper_in_raw():
    turn = {"response": {"sender": "human", "message": "hi"}, "share_link": ""}
    message = schema.parse_message(turn)
    assert (message.role, message.text) == ("user", "hi")
    assert message.raw is turn


def test_conversation_meta_merges_the_wrapper():
    entry = {"conversation": {"id": "a", "title": "T"}, "responses": []}
    meta = schema.conversation_meta(entry)
    assert meta["id"] == "a" and meta["title"] == "T" and meta["responses"] == []


def test_conversation_meta_lets_outer_keys_win():
    entry = {"conversation": {"title": "inner"}, "title": "outer"}
    assert schema.conversation_meta(entry)["title"] == "outer"


def test_official_export_layout_is_recognised():
    found = list(official.walk_conversations(XAI_EXPORT))
    assert len(found) == 1


def test_official_export_parses_roles_and_nested_timestamps(tmp_path):
    path = tmp_path / "prod-grok-backend.json"
    path.write_text(json.dumps(XAI_EXPORT), encoding="utf-8")

    (conversation,) = official.load_conversations(path)
    assert conversation.id == "90804d85-4de3-477f-8598-77e008cd89c3"
    assert conversation.title == "EMA and RSI indicators"
    assert conversation.created == datetime(
        2026, 7, 28, 0, 29, 26, 9215, tzinfo=timezone.utc
    )
    assert [m.role for m in conversation.messages] == ["user", "assistant"]
    assert conversation.messages[0].created is not None


def test_official_export_converts_end_to_end(tmp_path):
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr(
            "ttl/30d/export_data/abc/prod-grok-backend.json", json.dumps(XAI_EXPORT)
        )
        handle.writestr("ttl/30d/export_data/abc/prod-mc-billing.json", "{}")

    out = tmp_path / "out"
    assert main(["convert", str(archive), "--out", str(out)]) == 0

    (written,) = list((out / "markdown").glob("*.md"))
    text = written.read_text()
    assert written.name.startswith("2026-07-28-ema-and-rsi-indicators")
    assert "## You" in text and "## Grok" in text
    # Every message survives verbatim; that is the property that matters.
    assert "How do I combine EMA with RSI?" in text
    assert "Use the EMA for trend and RSI for timing." in text


# --------------------------------------------------------------------------
# merging near-duplicate conversations
# --------------------------------------------------------------------------


def _conversation(cid, title, texts, created=None):
    return schema.Conversation(
        id=cid,
        title=title,
        created=created or datetime(2026, 1, 1, tzinfo=timezone.utc),
        messages=[schema.Message(role="user", text=t) for t in texts],
    )


def test_tokenize_drops_stopwords_and_prompt_filler():
    tokens = merge.tokenize(
        "You are a professional expert; create me an irrigation plan"
    )
    assert "irrigation" in tokens
    for noise in ("you", "are", "professional", "expert", "create", "the"):
        assert noise not in tokens


def test_content_hash_ignores_message_order():
    left = _conversation("a", "T", ["one", "two"])
    right = _conversation("b", "T", ["two", "one"])
    assert merge.content_hash(left) == merge.content_hash(right)
    assert merge.content_hash(left) != merge.content_hash(
        _conversation("c", "T", ["x"])
    )


def test_cosine_of_identical_documents_is_one():
    (vector,) = merge.tfidf([Counter({"alpha": 1})])
    assert merge.cosine(vector, vector) == pytest.approx(1.0)


def test_exact_duplicates_collapse_keeping_the_earliest():
    early = _conversation(
        "early", "Passport", ["same body"], datetime(2026, 5, 27, tzinfo=timezone.utc)
    )
    late = _conversation(
        "late", "Passport", ["same body"], datetime(2026, 7, 28, tzinfo=timezone.utc)
    )
    (group,) = merge.group_conversations([late, early])

    assert [c.id for c in group.conversations] == ["early"]
    assert [c.id for c in group.duplicates] == ["late"]


def test_similar_conversations_merge_and_unrelated_ones_do_not():
    anime_a = _conversation(
        "a", "Free anime streaming sites", ["free anime streaming website list"]
    )
    anime_b = _conversation(
        "b", "Best free anime streaming websites", ["best free anime streaming website"]
    )
    mazda = _conversation(
        "c", "Mazda door lock fault", ["car door lock fuse box clicking"]
    )

    groups = merge.group_conversations([anime_a, anime_b, mazda])
    sizes = sorted(len(group.conversations) for group in groups)
    assert sizes == [1, 2]
    merged = next(g for g in groups if len(g.conversations) == 2)
    assert {c.id for c in merged.conversations} == {"a", "b"}


def test_grouping_is_transitive():
    """Single-link: A~B and B~C puts all three together even if A and C differ."""
    a = _conversation("a", "irrigation drip system", ["drip irrigation tubing layout"])
    b = _conversation(
        "b", "irrigation and mushroom farm", ["drip irrigation mushroom substrate"]
    )
    c = _conversation(
        "c", "mushroom substrate", ["mushroom substrate inoculation spawn"]
    )

    groups = merge.group_conversations([a, b, c], threshold=0.15)
    assert len(groups) == 1
    assert len(groups[0].conversations) == 3


def test_every_conversation_survives_grouping():
    conversations = [
        _conversation(str(i), f"Topic {i}", [f"body {i}"]) for i in range(7)
    ]
    groups = merge.group_conversations(conversations)
    recovered = {c.id for g in groups for c in g.conversations}
    assert recovered == {str(i) for i in range(7)}


def test_group_conversations_on_empty_input():
    assert merge.group_conversations([]) == []


def test_group_is_labelled_by_its_richest_conversation():
    small = _conversation("s", "Short", ["a"])
    big = _conversation("b", "The detailed one", ["a", "b", "c"])
    group = merge.Group(conversations=[small, big])
    assert group.title == "The detailed one"
    assert group.message_count == 4


def test_render_group_nests_roles_under_conversations():
    group = merge.Group(
        conversations=[
            _conversation(
                "a", "First", ["hello"], datetime(2026, 1, 2, tzinfo=timezone.utc)
            ),
            _conversation(
                "b", "Second", ["world"], datetime(2026, 3, 4, tzinfo=timezone.utc)
            ),
        ]
    )
    text = merge.render_group(group)

    assert "merged_from: 2" in text
    assert "## 2026-01-02 — First" in text
    assert "## 2026-03-04 — Second" in text
    # Roles sit a level below the conversation headings, so a message that
    # contains its own "## " cannot be mistaken for a conversation boundary.
    assert "### You" in text
    assert "\n## You" not in text
    assert "hello" in text and "world" in text


def test_render_group_notes_collapsed_duplicates():
    group = merge.Group(
        conversations=[_conversation("a", "Passport", ["body"])],
        duplicates=[_conversation("b", "Passport", ["body"])],
    )
    text = merge.render_group(group)
    assert "exact_duplicates_collapsed: 1" in text
    assert "1 exact duplicate(s) collapsed" in text


def test_group_stem_leads_with_the_month():
    group = merge.Group(
        conversations=[
            _conversation(
                "a", "Child Support", ["x"], datetime(2026, 3, 9, tzinfo=timezone.utc)
            )
        ]
    )
    assert merge.group_stem(group) == "2026-03-child-support"


def test_summarize_reports_duplicates_and_merges():
    group = merge.Group(
        conversations=[
            _conversation("a", "Passport", ["b"]),
            _conversation("c", "Passport 2", ["b2"]),
        ],
        duplicates=[_conversation("d", "Passport", ["b"])],
    )
    report = merge.summarize([group])
    assert "1 exact duplicate(s) collapsed." in report
    assert "Passport" in report


# --------------------------------------------------------------------------
# cli: merge, and the archive round-trip
# --------------------------------------------------------------------------


def _export_fixture(tmp_path):
    source = tmp_path / "dump.json"
    source.write_text(json.dumps(XAI_EXPORT), encoding="utf-8")
    return source


def test_convert_then_render_round_trips_without_losing_messages(tmp_path):
    """Regression: `convert` archived a bare entry that `render` read as empty."""
    out = tmp_path / "out"
    assert main(["convert", str(_export_fixture(tmp_path)), "--out", str(out)]) == 0

    for path in (out / "markdown").glob("*.md"):
        path.unlink()
    assert main(["render", "--out", str(out)]) == 0

    (rendered,) = list((out / "markdown").glob("*.md"))
    text = rendered.read_text()
    assert "_No messages were returned" not in text
    assert "How do I combine EMA with RSI?" in text


def test_load_raw_accepts_a_bare_entry(tmp_path):
    """Archives written before the envelope was consistent still load."""
    out = tmp_path / "out"
    render.write_raw(out / "raw", "conv-1", XAI_EXPORT["conversations"][0])

    assert main(["render", "--out", str(out)]) == 0
    (rendered,) = list((out / "markdown").glob("*.md"))
    assert "How do I combine EMA with RSI?" in rendered.read_text()


def test_merge_writes_one_document_per_group(tmp_path):
    out = tmp_path / "out"
    assert main(["convert", str(_export_fixture(tmp_path)), "--out", str(out)]) == 0
    assert main(["merge", "--out", str(out)]) == 0

    (merged,) = list((out / "merged").glob("*.md"))
    assert "merged_from: 1" in merged.read_text()


def test_merge_dry_run_writes_nothing(tmp_path, capsys):
    out = tmp_path / "out"
    main(["convert", str(_export_fixture(tmp_path)), "--out", str(out)])

    assert main(["merge", "--out", str(out), "--dry-run"]) == 0
    assert not (out / "merged").exists()
    assert "dry run" in capsys.readouterr().err


def test_merge_collapses_a_duplicated_conversation(tmp_path, capsys):
    """The real export had one conversation saved twice, byte for byte."""
    twice = json.loads(json.dumps(XAI_EXPORT))
    clone = json.loads(json.dumps(twice["conversations"][0]))
    clone["conversation"]["id"] = "second-copy"
    clone["conversation"]["create_time"] = "2026-08-01T00:00:00Z"
    twice["conversations"].append(clone)

    source = tmp_path / "dump.json"
    source.write_text(json.dumps(twice), encoding="utf-8")
    out = tmp_path / "out"

    assert main(["convert", str(source), "--out", str(out)]) == 0
    assert main(["merge", "--out", str(out)]) == 0

    assert "1 exact duplicate(s) collapsed." in capsys.readouterr().err
    (merged,) = list((out / "merged").glob("*.md"))
    assert "exact_duplicates_collapsed: 1" in merged.read_text()


def test_merge_without_an_archive_fails_cleanly(tmp_path, capsys):
    assert main(["merge", "--out", str(tmp_path / "nothing")]) == 1
    assert "Run `pull` or `convert` first" in capsys.readouterr().err


def test_merge_is_idempotent(tmp_path):
    """Regression: re-running appended a fresh copy of every merged document."""
    out = tmp_path / "out"
    main(["convert", str(_export_fixture(tmp_path)), "--out", str(out)])

    main(["merge", "--out", str(out)])
    first = sorted(p.name for p in (out / "merged").glob("*.md"))
    main(["merge", "--out", str(out)])
    second = sorted(p.name for p in (out / "merged").glob("*.md"))

    assert first == second


def test_merge_removes_documents_for_groups_that_are_gone(tmp_path):
    out = tmp_path / "out"
    merged = out / "merged"
    merged.mkdir(parents=True)
    (merged / "2020-01-stale-topic.md").write_text("old", encoding="utf-8")

    main(["convert", str(_export_fixture(tmp_path)), "--out", str(out)])
    main(["merge", "--out", str(out)])

    assert not (merged / "2020-01-stale-topic.md").exists()
    assert list(merged.glob("*.md"))


def test_write_groups_disambiguates_same_named_groups_within_a_run(tmp_path):
    same = datetime(2026, 5, 1, tzinfo=timezone.utc)
    groups = [
        merge.Group(conversations=[_conversation("a", "Same Title", ["one"], same)]),
        merge.Group(conversations=[_conversation("b", "Same Title", ["two"], same)]),
    ]
    written = merge.write_groups(tmp_path, groups)
    assert len({p.name for p in written}) == 2
