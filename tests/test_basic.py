import os
import time

import pytest

os.environ["SPAREWHEEL_AUDIO_DIR"] = "/tmp/sparewheel-test-audio"

from sparewheel import config, player  # noqa: E402


def test_safe_name_strips_path_and_rejects_non_audio():
    assert player.safe_name("../../etc/my song.mp3") == "my_song.mp3"
    with pytest.raises(ValueError):
        player.safe_name("evil.sh")


def test_current_file_is_newest(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    assert player.current_file() is None
    a, b = tmp_path / "a.mp3", tmp_path / "b.wav"
    a.write_bytes(b"x"); time.sleep(0.01); b.write_bytes(b"x")
    assert player.current_file() == b


def test_clear_audio_dir_removes_old_audio(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path)
    (tmp_path / "old.mp3").write_bytes(b"x")
    (tmp_path / "half.wav.part").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")
    (tmp_path / "new.ogg").write_bytes(b"x")
    player.clear_audio_dir(keep=tmp_path / "new.ogg")
    assert sorted(p.name for p in tmp_path.iterdir()) == ["new.ogg", "notes.txt"]
