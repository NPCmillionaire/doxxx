from doxxx.core import helpers as hl
from doxxx.utils import update as upd
import subprocess

def test_default_config():
    configs = hl.load_config()
    assert "auto_update_status" in configs
    # Make sure config.json has "auto_update_status" set to true
    assert configs["auto_update_status"]


def test_config_json(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    monkeypatch.setenv("DOXX_CONFIG", str(cfg))
    configs = hl.load_config()
    assert "auto_update_status" in configs
    # Should be default True
    assert configs["auto_update_status"] is True


def test_config_set(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    monkeypatch.setenv("DOXX_CONFIG", str(cfg))

    def get_status():
        return hl.load_config()["auto_update_status"]

    hl.save_config_value("auto_update_status", False)
    assert get_status() is False

    hl.save_config_value("auto_update_status", True)
    assert get_status() is True

def test_update_self_prints_message_on_install_failure(monkeypatch, capsys):
    calls = []

    def fake_check_call(cmd, *a, **kw):
        calls.append(cmd)
        if "uninstall" in cmd:
            return 0
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(subprocess, "check_call", fake_check_call)

    upd.update_self()

    out = capsys.readouterr().out
    assert "Failed to update doxxx" in out
    assert len(calls) == 1
    assert calls[0][-1] == upd.GIT_URL
