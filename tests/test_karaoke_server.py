"""Rules for the shared karaoke leaderboard.

Exercises the board directly rather than over a socket, so the suite stays
offline. The HTTP layer above it is a thin shell around these calls.
"""

import json

import pytest

from tools.karaoke_server.board import (
    MAX_ENTRIES,
    MAX_NAME,
    Board,
    ValidationError,
    clean_entry,
)


def run(**over):
    entry = {"score": 80, "title": "Twinkle, Twinkle, Little Star", "name": "Jay"}
    entry.update(over)
    return entry


# ---------- validation ----------


def test_minimal_run_is_accepted():
    entry = clean_entry(run())
    assert entry["score"] == 80
    assert entry["name"] == "Jay"
    assert entry["tempo"] == 100
    assert entry["part"] == "a"
    assert entry["duet"] is False


def test_score_and_title_are_required():
    with pytest.raises(ValidationError):
        clean_entry({"title": "no score"})
    with pytest.raises(ValidationError):
        clean_entry({"score": 50})


@pytest.mark.parametrize("bad", [-1, 101, 1000])
def test_score_must_be_in_range(bad):
    with pytest.raises(ValidationError):
        clean_entry(run(score=bad))


def test_missing_name_falls_back():
    assert clean_entry(run(name=None))["name"] == "You"
    assert clean_entry(run(name="   "))["name"] == "You"


def test_long_name_is_capped():
    assert len(clean_entry(run(name="x" * 200))["name"]) == MAX_NAME


def test_control_characters_are_stripped():
    entry = clean_entry(run(name="Jay\x00\x1b[31m\nHacker"))
    assert "\x00" not in entry["name"]
    assert "\n" not in entry["name"]
    assert entry["name"].startswith("Jay")


def test_markup_in_a_name_is_kept_as_text_not_rejected():
    # storage keeps it verbatim; the page renders through textContent
    entry = clean_entry(run(name="<script>x</script>"))
    assert entry["name"] == "<script>x</script>"[:MAX_NAME]


def test_client_timestamp_is_ignored():
    entry = clean_entry(run(at="1999-01-01T00:00:00+00:00"))
    assert not entry["at"].startswith("1999")


def test_booleans_are_not_accepted_as_scores():
    with pytest.raises(ValidationError):
        clean_entry(run(score=True))


def test_unknown_part_falls_back_to_a():
    assert clean_entry(run(part="z"))["part"] == "a"
    assert clean_entry(run(part="b"))["part"] == "b"


def test_non_object_payload_is_rejected():
    with pytest.raises(ValidationError):
        clean_entry([1, 2, 3])


# ---------- ordering and storage ----------


def test_board_orders_by_score(tmp_path):
    board = Board(tmp_path / "s.json")
    for score in (40, 90, 65):
        board.add(run(score=score))
    assert [e["score"] for e in board.top()] == [90, 65, 40]


def test_ties_keep_the_earlier_run_first(tmp_path):
    board = Board(tmp_path / "s.json")
    first = board.add(run(score=70, name="First"))
    second = board.add(run(score=70, name="Second"))
    top = board.top()
    assert [e["name"] for e in top[:2]] == ["First", "Second"]
    assert first["at"] <= second["at"]


def test_top_survives_a_reopen(tmp_path):
    path = tmp_path / "s.json"
    Board(path).add(run(score=77))
    assert Board(path).top()[0]["score"] == 77


def test_board_is_capped(tmp_path):
    board = Board(tmp_path / "s.json")
    for i in range(MAX_ENTRIES + 25):
        board.add(run(score=i % 101))
    rows = json.loads((tmp_path / "s.json").read_text(encoding="utf-8"))
    assert len(rows) == MAX_ENTRIES
    # the cap keeps the best, not the most recent
    assert rows[0]["score"] == 100


def test_limit_is_clamped(tmp_path):
    board = Board(tmp_path / "s.json")
    for _ in range(5):
        board.add(run())
    assert len(board.top(0)) == 1
    assert len(board.top(9999)) == 5


def test_missing_file_reads_as_empty(tmp_path):
    assert Board(tmp_path / "nope.json").top() == []


def test_corrupt_file_does_not_raise(tmp_path):
    path = tmp_path / "s.json"
    path.write_text("{ this is not json", encoding="utf-8")
    board = Board(path)
    assert board.top() == []
    board.add(run(score=55))
    assert board.top()[0]["score"] == 55


def test_junk_rows_are_skipped(tmp_path):
    path = tmp_path / "s.json"
    path.write_text('[1, "two", {"no_score": 1}, {"score": 9, "title": "ok"}]', "utf-8")
    assert [e["score"] for e in Board(path).top()] == [9]


def test_clear_empties_the_board(tmp_path):
    board = Board(tmp_path / "s.json")
    board.add(run())
    board.clear()
    assert board.top() == []


def test_write_is_atomic_leaving_no_temp_files(tmp_path):
    board = Board(tmp_path / "s.json")
    board.add(run())
    assert [p.name for p in tmp_path.iterdir()] == ["s.json"]


# ---------- the served document ----------


def test_page_is_wrapped_as_a_standalone_document():
    from tools.karaoke_server.server import page_html

    out = page_html("<title>K</title>\n<style>body{}</style>\n<div>hi</div>")
    assert out.startswith("<!doctype html>")
    assert 'name="karaoke-board"' in out
    # styles belong to the head, markup to the body
    head, body = out.split("</head>", 1)
    assert "<style>body{}</style>" in head
    assert "<div>hi</div>" in body


def test_page_without_a_stylesheet_still_wraps():
    from tools.karaoke_server.server import page_html

    out = page_html("<div>bare</div>")
    assert out.startswith("<!doctype html>")
    assert "<div>bare</div>" in out


def test_the_real_page_carries_the_board_marker():
    from tools.karaoke_server.server import PAGE, page_html

    if not PAGE.exists():
        pytest.skip("karaoke page not present")
    out = page_html()
    assert out.startswith("<!doctype html>")
    assert 'content="/api/scores"' in out
