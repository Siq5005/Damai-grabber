import time

import ntplib


class NTPTimer:
    def __init__(self, servers: list[str], timeout: int = 3):
        self.servers = servers
        self.timeout = timeout
        self.offset: float = 0.0

    def sync(self) -> float:
        client = ntplib.NTPClient()
        for server in self.servers:
            try:
                response = client.request(server, version=3, timeout=self.timeout)
                self.offset = response.offset
                return self.offset
            except Exception:
                continue
        self.offset = 0.0
        return 0.0

    def now(self) -> float:
        return time.time() + self.offset

    def wait_until(self, target: float) -> None:
        while True:
            remaining = target - self.now()
            if remaining <= 0:
                return
            if remaining > 0.05:
                time.sleep(remaining - 0.05)
