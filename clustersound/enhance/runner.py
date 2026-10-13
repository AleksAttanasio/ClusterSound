"""Runs one enhancement job in a child process (worker.py) and follows it.

A separate process because torch keeps freed GPU/CPU memory cached for the life of the process: when the worker
exits, everything it took goes back to the system, and the app never imports torch at all.
"""
import json
import os
import queue
import subprocess
import sys
import threading
from collections import deque
from typing import Callable

WORKER_FLAG = "--enhance-worker"  # the frozen app re-runs itself as the worker (__main__.py)


class Cancelled(Exception):
    pass


def command(model: str, src: str, dst: str) -> list[str]:
    head = [sys.executable, WORKER_FLAG] if getattr(sys, "frozen", False) else \
        [sys.executable, "-m", "clustersound.enhance.worker"]
    return head + ["--model", model, src, dst]


def run(model: str, src: str, dst: str, on_progress: Callable[[float], None] | None = None,
        cancelled: Callable[[], bool] | None = None, cmd: list[str] | None = None) -> dict:
    """Enhance src into dst; returns the worker's last message ({"done", "sr"}). Raises Cancelled, or RuntimeError
    with the worker's error. On cancel or error dst is removed."""
    env = {**os.environ, "PYTORCH_ENABLE_MPS_FALLBACK": "1"}  # ops MPS lacks run on the CPU instead of failing
    p = subprocess.Popen(cmd or command(model, src, dst), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace", env=env,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))  # Windows: no console window
    lines: queue.Queue = queue.Queue()
    err_tail: deque = deque(maxlen=20)

    def read_out():
        for line in p.stdout:
            lines.put(line)
    threading.Thread(target=read_out, daemon=True).start()
    threading.Thread(target=lambda: err_tail.extend(p.stderr), daemon=True).start()
    last: dict = {}
    try:
        while True:
            if cancelled and cancelled():
                raise Cancelled()
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                if p.poll() is not None and lines.empty():
                    break
                continue
            try:
                msg = json.loads(line)
            except ValueError:
                continue  # stray output from a library
            if "progress" in msg and on_progress:
                on_progress(float(msg["progress"]))
            if "done" in msg or "error" in msg:
                last = msg
        p.wait()
        if "error" in last:
            raise RuntimeError(last["error"])
        if p.returncode != 0 or "done" not in last:
            tail = "".join(err_tail).strip().splitlines()
            raise RuntimeError(tail[-1] if tail else f"il processo è terminato con codice {p.returncode}")
        return last
    except BaseException:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
        if os.path.exists(dst):
            os.remove(dst)
        raise
