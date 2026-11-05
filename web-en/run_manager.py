"""Spawns and supervises worker processes; stores and fans out their events.

One run at a time (the Ditto model needs the GPU). Events are kept in memory,
persisted to runtime/runs/<id>/events.jsonl, and streamed to browsers via SSE.
"""
import collections
import json
import os
import subprocess
import sys
import threading
import time
import uuid

import config

WORKER = os.path.join(config.HERE, "worker.py")
TERMINAL = ("done", "error", "stopped")
LOG_KEEP = 3000


class Run:
    def __init__(self, run_id, params):
        self.id = run_id
        self.params = params
        self.state = "starting"
        self.started_at = time.time()
        self.ended_at = None
        self.events = []  # persisted-type events, each with "seq"
        self.logs = collections.deque(maxlen=LOG_KEEP)  # (n, line)
        self.log_n = 0
        self.cond = threading.Condition()
        self.proc = None
        self.topic = None
        self.transport = None
        self.dir = os.path.join(config.RUNS_DIR, run_id)

    def summary(self):
        incs = [e for e in self.events if e["type"] == "increment"]
        return {
            "id": self.id, "state": self.state, "params": self.params,
            "started_at": self.started_at, "ended_at": self.ended_at,
            "increments": len(incs), "transport": self.transport,
        }


class RunManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._runs = {}
        self._active = None
        os.makedirs(config.RUNS_DIR, exist_ok=True)

    # -- public API -------------------------------------------------------
    def start(self, params):
        with self._lock:
            if self._active and self._active.state not in TERMINAL:
                raise RuntimeError("A run is already in progress.")
            run_id = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
            run = Run(run_id, params)
            os.makedirs(run.dir, exist_ok=True)
            params_path = os.path.join(run.dir, "params.json")
            with open(params_path, "w", encoding="utf-8") as fh:
                json.dump(params, fh)
            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
            run.proc = subprocess.Popen(
                [sys.executable, "-u", WORKER, params_path, run_id],
                cwd=config.REPO_ROOT, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            self._runs[run_id] = run
            self._active = run
        self._write_meta(run)
        self._push(run, {"type": "status", "state": "starting", "message": "Process started (pid %d)." % run.proc.pid})
        threading.Thread(target=self._read_events, args=(run,), daemon=True).start()
        threading.Thread(target=self._read_logs, args=(run,), daemon=True).start()
        threading.Thread(target=self._supervise, args=(run,), daemon=True).start()
        return run

    def stop(self, run_id):
        run = self.get(run_id)
        if not run or run.state in TERMINAL or not run.proc:
            return False
        run.proc.terminate()
        self._finish(run, "stopped", {"type": "stopped"})
        return True

    def get(self, run_id):
        run = self._runs.get(run_id)
        if run:
            return run
        return self._load(run_id)

    def active(self):
        return self._active if self._active and self._active.state not in TERMINAL else None

    def history(self, limit=30):
        out = {r.id: r.summary() for r in self._runs.values()}
        if os.path.isdir(config.RUNS_DIR):
            for rid in os.listdir(config.RUNS_DIR):
                if rid in out:
                    continue
                meta = os.path.join(config.RUNS_DIR, rid, "meta.json")
                if os.path.isfile(meta):
                    try:
                        with open(meta, encoding="utf-8") as fh:
                            out[rid] = json.load(fh)
                    except (OSError, ValueError):
                        pass
        return sorted(out.values(), key=lambda r: r.get("started_at", 0), reverse=True)[:limit]

    def stream(self, run, after=0, after_log=0):
        """Yield ("event", ev) / ("logs", [lines]) / ("beat", None) until the run ends."""
        cursor, log_cursor = after, after_log
        while True:
            with run.cond:
                pending = [e for e in run.events if e["seq"] > cursor]
                fresh = [(n, l) for n, l in run.logs if n > log_cursor]
                if not pending and not fresh:
                    if run.state in TERMINAL:
                        return
                    run.cond.wait(timeout=15)
                    pending = [e for e in run.events if e["seq"] > cursor]
                    fresh = [(n, l) for n, l in run.logs if n > log_cursor]
                    if not pending and not fresh:
                        yield "beat", None
                        continue
            if fresh:
                log_cursor = fresh[-1][0]
                yield "logs", [l for _, l in fresh]
            for e in pending:
                cursor = e["seq"]
                yield "event", e

    # -- internals --------------------------------------------------------
    def _push(self, run, ev, persist=True):
        with run.cond:
            ev = dict(ev, seq=len(run.events) + 1, t=time.time())
            run.events.append(ev)
            if ev["type"] == "status":
                if run.state not in TERMINAL:
                    run.state = ev["state"]
            elif ev["type"] == "run_started" and run.state not in TERMINAL:
                run.state = "running"
            elif ev["type"] == "transport":
                run.transport = {"name": ev["name"], "note": ev["note"]}
                run.topic = ev.get("topic")
            run.cond.notify_all()
        if persist:
            try:
                with open(os.path.join(run.dir, "events.jsonl"), "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(ev, ensure_ascii=False) + "\n")
            except OSError:
                pass

    def _read_events(self, run):
        for raw in iter(run.proc.stdout.readline, b""):
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except ValueError:
                self._log(run, line)
                continue
            if ev.get("type") == "done":
                self._finish(run, "done", ev)
            elif ev.get("type") == "error":
                self._finish(run, "error", ev)
            else:
                self._push(run, ev)

    def _read_logs(self, run):
        with open(os.path.join(run.dir, "run.log"), "a", encoding="utf-8") as fh:
            for raw in iter(run.proc.stderr.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip()
                if line:
                    fh.write(line + "\n")
                    fh.flush()
                    self._log(run, line)

    def _log(self, run, line):
        with run.cond:
            run.log_n += 1
            run.logs.append((run.log_n, line))
            run.cond.notify_all()

    def _supervise(self, run):
        code = run.proc.wait()
        time.sleep(0.5)  # let reader threads drain
        if run.state not in TERMINAL:
            tail = "\n".join(l for _, l in list(run.logs)[-15:])
            self._finish(run, "error", {"type": "error",
                                        "message": "The process exited unexpectedly (code %s)." % code,
                                        "traceback": tail})
        self._cleanup_topic(run)

    def _finish(self, run, state, ev):
        with run.cond:
            if run.state in TERMINAL:
                return
            run.state = state
            run.ended_at = time.time()
        self._push(run, ev)
        with run.cond:
            run.cond.notify_all()
        self._write_meta(run)

    def _cleanup_topic(self, run):
        if run.topic:
            try:
                from confluent_kafka.admin import AdminClient
                import kafka_bus
                AdminClient({"bootstrap.servers": kafka_bus.BOOTSTRAP}).delete_topics([run.topic])
            except Exception:
                pass

    def _write_meta(self, run):
        try:
            with open(os.path.join(run.dir, "meta.json"), "w", encoding="utf-8") as fh:
                json.dump(run.summary(), fh)
        except OSError:
            pass

    def _load(self, run_id):
        d = os.path.join(config.RUNS_DIR, os.path.basename(run_id))
        meta, ev_path = os.path.join(d, "meta.json"), os.path.join(d, "events.jsonl")
        if not os.path.isfile(ev_path):
            return None
        try:
            with open(meta, encoding="utf-8") as fh:
                m = json.load(fh)
        except (OSError, ValueError):
            m = {}
        run = Run(run_id, m.get("params", {}))
        run.started_at = m.get("started_at", run.started_at)
        run.ended_at = m.get("ended_at")
        run.transport = m.get("transport")
        with open(ev_path, encoding="utf-8") as fh:
            run.events = [json.loads(l) for l in fh if l.strip()]
        # A persisted run whose process is gone can only be terminal.
        run.state = m.get("state") if m.get("state") in TERMINAL else "stopped"
        self._runs[run_id] = run
        return run
