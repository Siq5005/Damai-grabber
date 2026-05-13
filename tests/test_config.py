import json
from pathlib import Path

from utils.config import load_config, save_config, DEFAULT_CONFIG


def test_load_config_from_file(config_file, sample_config):
    config = load_config(config_file)
    assert config == sample_config


def test_load_config_missing_file_returns_defaults(tmp_path):
    path = tmp_path / "nonexistent.json"
    config = load_config(path)
    assert config == DEFAULT_CONFIG


def test_load_config_merges_partial_with_defaults(tmp_path):
    path = tmp_path / "partial.json"
    path.write_text(json.dumps({"debug_port": 9999}))
    config = load_config(path)
    assert config["debug_port"] == 9999
    assert config["grab"]["max_retries"] == DEFAULT_CONFIG["grab"]["max_retries"]
    assert config["ntp"]["servers"] == DEFAULT_CONFIG["ntp"]["servers"]


def test_save_config(tmp_path):
    path = tmp_path / "out.json"
    config = {"debug_port": 1234, "grab": {"max_retries": 5}}
    save_config(path, config)
    loaded = json.loads(path.read_text())
    assert loaded["debug_port"] == 1234
    assert loaded["grab"]["max_retries"] == 5
