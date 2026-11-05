"""X-TREATS web interface (Flask). Start with:  python web-en/app.py

Local tool: binds to 127.0.0.1 only. All code lives under web-en/ and the
rest of the repository is used read-only (the worker imports X_TREATS_run_gpu.py
without modifying it).
"""
import json
import os
import shutil
import sys

from flask import Flask, Response, jsonify, request, send_from_directory

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: E402
import datasets_store as store  # noqa: E402
import kafka_bus  # noqa: E402
from run_manager import RunManager  # noqa: E402

app = Flask(__name__, static_folder="static", static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = int(6.5 * 1024 ** 3)  # per-kind limits are enforced in api_upload
manager = RunManager()


@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/api/config")
def api_config():
    cfg = config.public_config()
    ok, detail = kafka_bus.kafka_available(timeout=2.0)
    cfg["kafka"] = {"available": ok, "detail": detail}
    active = manager.active()
    cfg["active_run"] = active.id if active else None
    return jsonify(cfg)


@app.route("/api/runs", methods=["GET"])
def api_runs():
    return jsonify(manager.history())


@app.route("/api/runs", methods=["POST"])
def api_start():
    # JSON-only: a cross-site <form> cannot send this content type, so a random
    # web page cannot make this local tool spawn a process.
    if not request.is_json:
        return jsonify(error="Content-Type must be application/json."), 415
    try:
        params = config.validate_params(request.get_json(silent=True) or {})
    except ValueError as e:
        return jsonify(error=str(e)), 400
    try:
        run = manager.start(params)
    except RuntimeError as e:
        return jsonify(error=str(e)), 409
    return jsonify(run.summary()), 201


@app.route("/api/runs/<run_id>")
def api_run(run_id):
    run = manager.get(run_id)
    if not run:
        return jsonify(error="Run not found."), 404
    return jsonify(dict(run.summary(), events=run.events, logs=[l for _, l in list(run.logs)[-300:]]))


@app.route("/api/runs/<run_id>/stop", methods=["POST"])
def api_stop(run_id):
    if not request.is_json:
        return jsonify(error="Content-Type must be application/json."), 415
    return jsonify(stopped=manager.stop(run_id))


@app.route("/api/runs/<run_id>/events")
def api_events(run_id):
    run = manager.get(run_id)
    if not run:
        return jsonify(error="Run not found."), 404
    after = int(request.headers.get("Last-Event-ID") or request.args.get("after") or 0)

    def gen():
        for kind, payload in manager.stream(run, after):
            if kind == "beat":
                yield ": keep-alive\n\n"
            elif kind == "logs":
                yield "event: log\ndata: %s\n\n" % json.dumps(payload, ensure_ascii=False)
            else:
                yield "id: %d\ndata: %s\n\n" % (payload["seq"], json.dumps(payload, ensure_ascii=False))
        yield "event: end\ndata: {}\n\n"

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ───────────── dataset / model uploads ─────────────
def _json_required():
    return None if request.is_json else (jsonify(error="Content-Type must be application/json."), 415)


@app.route("/api/datasets")
def api_datasets():
    return jsonify(config.public_config()["datasets"])


@app.route("/api/datasets/uploads", methods=["POST"])
def api_upload_start():
    bad = _json_required()
    if bad:
        return bad
    return jsonify(token=store.new_staging()), 201


@app.route("/api/datasets/uploads/<token>/<kind>", methods=["PUT"])
def api_upload(token, kind):
    """Raw-body upload (the browser sends the File itself): streamed to disk in 1 MB blocks."""
    if kind not in store.KINDS:
        return jsonify(error="Unknown file kind."), 404
    try:
        dest = store.staging_path(token, kind)
    except store.ValidationError as e:
        return jsonify(error=str(e)), 404
    limit = store.KINDS[kind][1]
    length = request.content_length
    if length is None:
        return jsonify(error="Content-Length header required."), 411
    if length > limit:
        return jsonify(error="File too large (limit %d MB)." % (limit // 1024 ** 2)), 413
    os.makedirs(store.UPLOADS_DIR, exist_ok=True)
    if shutil.disk_usage(store.UPLOADS_DIR).free < length * 1.2:
        return jsonify(error="Not enough free disk space for this upload."), 507
    part, written = dest + ".part", 0
    try:
        with open(part, "wb") as fh:
            while True:
                chunk = request.stream.read(1 << 20)
                if not chunk:
                    break
                written += len(chunk)
                if written > limit:
                    raise store.ValidationError("File too large (limit %d MB)." % (limit // 1024 ** 2))
                fh.write(chunk)
        if written != length:
            raise store.ValidationError("Upload interrupted (%d of %d bytes)." % (written, length))
        os.replace(part, dest)
        result = {"kind": kind, "bytes": written}
        if kind == "test":
            result.update(store.validate_dataset_file(dest))
        elif kind == "model":
            store.check_model_file(dest)
        return jsonify(result)
    except store.ValidationError as e:
        for path in (part, dest):
            if os.path.exists(path):
                os.remove(path)
        return jsonify(error=str(e)), 422


@app.route("/api/datasets/uploads/<token>/commit", methods=["POST"])
def api_upload_commit(token):
    bad = _json_required()
    if bad:
        return bad
    try:
        meta = store.commit(token, request.get_json(silent=True) or {}, config.REPO_ROOT)
    except store.ValidationError as e:
        return jsonify(error=str(e)), 422
    return jsonify(meta), 201


@app.route("/api/datasets/uploads/<token>", methods=["DELETE"])
def api_upload_cancel(token):
    try:
        shutil.rmtree(store.staging_path(token), ignore_errors=True)
    except store.ValidationError:
        pass
    return jsonify(cancelled=True)


@app.route("/api/datasets/<name>", methods=["DELETE"])
def api_dataset_delete(name):
    active = manager.active()
    if active and (active.params or {}).get("dataset") == name:
        return jsonify(error="This dataset is being used by the current run."), 409
    try:
        store.delete(name)
    except store.ValidationError as e:
        return jsonify(error=str(e)), 404
    return jsonify(deleted=name)


if __name__ == "__main__":
    port = int(os.environ.get("XTREATS_WEB_PORT", "5051"))
    print("X-TREATS web: http://127.0.0.1:%d" % port)
    app.run(host="127.0.0.1", port=port, threaded=True, debug=False)
