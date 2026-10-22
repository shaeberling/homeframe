import os

from homeframe.app import files_fingerprint


def test_fingerprint_follows_edits_additions_and_removals(tmp_path):
    (tmp_path / "app.js").write_text("one")
    first = files_fingerprint(tmp_path)
    assert files_fingerprint(tmp_path) == first

    (tmp_path / "app.js").write_text("two!")
    edited = files_fingerprint(tmp_path)
    assert edited != first

    (tmp_path / "icons").mkdir()
    (tmp_path / "icons" / "new.svg").write_text("<svg/>")
    added = files_fingerprint(tmp_path)
    assert added != edited

    (tmp_path / "icons" / "new.svg").unlink()
    assert files_fingerprint(tmp_path) == edited


def test_fingerprint_sees_a_save_that_keeps_the_size(tmp_path):
    page = tmp_path / "index.html"
    page.write_text("aaaa")
    os.utime(page, ns=(1_000_000_000, 1_000_000_000))
    before = files_fingerprint(tmp_path)
    page.write_text("bbbb")
    os.utime(page, ns=(2_000_000_000, 2_000_000_000))
    assert files_fingerprint(tmp_path) != before
