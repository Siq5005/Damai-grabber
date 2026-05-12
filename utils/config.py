import json
import copy
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, Any] = {
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


def _deep_merge(base: dict, override: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(path: Path) -> dict:
    if not path.exists():
        return copy.deepcopy(DEFAULT_CONFIG)
    with open(path, "r", encoding="utf-8") as f:
        user_config = json.load(f)
    return _deep_merge(DEFAULT_CONFIG, user_config)


def save_config(path: Path, config: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
