import json
import time

import pytest

from sparewheel import config, player


@pytest.fixture(autouse=True)
def dirs(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "AUDIO_DIR", tmp_path / "audio")
    monkeypatch.setattr(config, "MPV_CONFIG", tmp_path / "audio" / "mpv_config.json")
    (tmp_path / "audio" / "test").mkdir(parents=True)
    (tmp_path / "audio" / "playback").mkdir()
    return tmp_path / "audio"  # playback files go in dirs/"playback", test in dirs/"test"


def test_safe_name_strips_path_and_rejects_non_audio():
    assert player.safe_name("../../etc/my song.mp3") == "my_song.mp3"
    with pytest.raises(ValueError):
        player.safe_name("evil.sh")


def test_slots_are_separate_and_newest_wins(dirs):
    assert player.current_file("playback") is None
    (dirs / "playback" / "a.mp3").write_bytes(b"x"); time.sleep(0.01); (dirs / "playback" / "b.wav").write_bytes(b"x")
    (dirs / "test" / "t.ogg").write_bytes(b"x")
    assert player.current_file("playback").name == "b.wav"
    assert player.current_file("test").name == "t.ogg"


def test_clear_slot_keeps_new_file_other_slot_and_non_audio(dirs):
    (dirs / "playback" / "old.mp3").write_bytes(b"x"); (dirs / "playback" / "half.wav.part").write_bytes(b"x")
    (dirs / "playback" / "notes.txt").write_bytes(b"x"); (dirs / "playback" / "new.ogg").write_bytes(b"x")
    (dirs / "test" / "t.mp3").write_bytes(b"x")
    player.clear_slot("playback", keep=dirs / "playback" / "new.ogg")
    assert sorted(p.name for p in (dirs / "playback").iterdir()) == ["new.ogg", "notes.txt"]
    assert (dirs / "test" / "t.mp3").exists()


def test_volume_config_roundtrip_and_defaults():
    assert player.load_config() == {"volume": 100}  # no file
    player.save_config(37)
    assert json.loads(config.MPV_CONFIG.read_text()) == {"volume": 37}
    assert player.load_config() == {"volume": 37}
    config.MPV_CONFIG.write_text("garbage")
    assert player.load_config() == {"volume": 100}


def test_mpv_launched_looping_with_saved_volume_and_ipc(dirs, monkeypatch):
    (dirs / "playback" / "a.mp3").write_bytes(b"x")
    player.save_config(42)
    captured = {}

    class P:
        def poll(self): return None
        def terminate(self): pass
        def wait(self, timeout=None): pass

    monkeypatch.setattr(player.subprocess, "Popen", lambda args: captured.setdefault("args", args) and P())
    monkeypatch.setattr(player, "_force_alsa_mixer_to_max", lambda: None)
    assert player.play("playback") == "a.mp3"
    assert "--volume=42" in captured["args"] and "--loop-file=inf" in captured["args"]
    assert any(a.startswith("--input-ipc-server=") for a in captured["args"])
    sent = []
    monkeypatch.setattr(player, "_ipc", sent.append)
    player.set_volume(10, persist=False)
    assert sent == [["set_property", "volume", 10]] and player.load_config()["volume"] == 42  # live only
    player.set_volume(20, persist=True)
    assert player.load_config()["volume"] == 20


def test_hwclock_output_is_shown_in_utc():
    from sparewheel import rtc

    assert rtc.parse_hwclock("2026-11-09 22:51:16.691963+01:00") == "2026-11-09T21:51:16+00:00"
    assert rtc.parse_hwclock("weird output") == "weird output"
