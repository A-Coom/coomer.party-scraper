import time
from threading import Lock

class RateLimiter:
    def __init__(self, requests_per_second: int = 2):
        self.requests_per_second = requests_per_second
        self.min_interval = 1.0 / requests_per_second if requests_per_second > 0 else 0
        self.last_request_time = 0.0
        self.lock = Lock()

    def wait(self):
        if self.requests_per_second <= 0:
            return

        with self.lock:
            current_time = time.monotonic()
            time_since_last_request = current_time - self.last_request_time

            if time_since_last_request < self.min_interval:
                sleep_time = self.min_interval - time_since_last_request
                time.sleep(sleep_time)

            # update using monotonic time
            self.last_request_time = time.monotonic()
