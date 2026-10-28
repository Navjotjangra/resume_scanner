"""Scan worker thread and queue messages for the GUI.

The worker thread never touches Tkinter widgets. It pulls from the
pipeline and posts Progress / Finished / Failed / Cancelled messages to
a queue.Queue, which the GUI polls on the main thread via root.after.
"""

from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass

from scanner.pipeline import scan_and_rank
from scanner.models import ScanReport
from scanner.errors import ScanCancelled, ScannerError


@dataclass
class Progress:
    done: int
    total: int
    name: str


@dataclass
class Finished:
    report: ScanReport


@dataclass
class Failed:
    message: str


@dataclass
class Cancelled:
    pass


class ScanWorker(threading.Thread):
    """Background thread that runs scan_and_rank and posts results to a queue."""

    def __init__(
        self,
        jd: str,
        paths: list,
        out_queue: "queue.Queue[Progress | Finished | Failed | Cancelled]",
        cancel_event: threading.Event,
    ) -> None:
        super().__init__(daemon=True)
        self.jd = jd
        self.paths = paths
        self.out_queue = out_queue
        self.cancel_event = cancel_event

    def run(self) -> None:  # noqa: D401 - thread entry point
        try:
            report = scan_and_rank(
                self.jd,
                self.paths,
                on_progress=self._on_progress,
                cancel=self.cancel_event,
            )
            self.out_queue.put(Finished(report))
        except ScanCancelled:
            self.out_queue.put(Cancelled())
        except ScannerError as e:
            self.out_queue.put(Failed(str(e)))
        except Exception:  # noqa: BLE001 - boundary; never crash the worker
            logging.exception("Unexpected error during scan")
            self.out_queue.put(Failed("Unexpected error. See logs."))

    def _on_progress(self, done: int, total: int, name: str) -> None:
        self.out_queue.put(Progress(done, total, name))
