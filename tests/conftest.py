import json
import pytest
from pathlib import Path


@pytest.fixture
def sample_config():
    return {
        "chrome_path": "",
        "debug_port": 9222,
        "grab": {
            "max_retries": 3,
            "retry_interval_ms": 500,
            "poll_interval_ms": 50,
            "confirm_timeout_ms": 5000,
        },
        "ntp": {
            "servers": ["ntp.aliyun.com", "ntp.tencent.com", "cn.pool.ntp.org"],
            "timeout_s": 3,
        },
    }


@pytest.fixture
def config_file(tmp_path, sample_config):
    path = tmp_path / "config.json"
    path.write_text(json.dumps(sample_config, indent=2))
    return path
