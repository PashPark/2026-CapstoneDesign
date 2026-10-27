import threading
import requests


class SeatPublisher:
    def __init__(self, cfg, stop_event):
        self.cfg = cfg
        self.stop_event = stop_event
        self.snapshot = None
        self.pending = threading.Event()
        self.ready = threading.Event()
        self.ready.set()
        self.last_status = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        with requests.Session() as session:
            while not self.stop_event.is_set():
                if not self.pending.wait(timeout=0.1):
                    continue
                self.pending.clear()
                try:
                    self.last_status = session.post(
                        self.cfg.flask_url, json=self.snapshot, timeout=0.3
                    ).status_code
                except requests.RequestException:
                    self.last_status = None
                self.ready.set()
