# X-TREATS · web interface (English)

Local console to run X-TREATS by choosing the parameters in the browser and
watching every processed increment in real time. The Portuguese version lives in
`../web-pt` (same features, same backend logic; only the language differs).

**Everything lives in `web-en/`.** The rest of the repository is read-only: the
worker *imports* `X_TREATS_run_gpu.py` without modifying it. (The legacy Flask app in
`web/` is untouched.)

## Run

```powershell
powershell -File web-en\start.ps1      # picks the Python that has flask+lemon+torch
# or, with the right Python 3.7:
python web-en\app.py                    # http://127.0.0.1:5051  (XTREATS_WEB_PORT changes the port)
```

Requirements: the same as the project (Ditto in `..\ditto`, GNEM in `..\GNEM`,
`checkpoints\`, `data\er_magellan\Structured\`, `lemon`) plus Flask and `confluent-kafka`
(already in the environment). No new dependencies; the front end is plain JS, no CDN.

Kafka is optional: `docker compose -f kafka/docker-compose.yaml up -d` starts the broker
on `localhost:9092`. Without a broker, micro-batches travel through an in-memory queue
(the badge at the top of the page shows which transport is active).

## How it works

```
Browser ──POST /api/runs──▶ app.py ──▶ run_manager ──spawn──▶ worker.py (own process, cwd = repo root)
    ▲                                        │ stdout: JSON events        ├─ Producer: sends 1 micro-batch every τ s ──┐
    └────────── SSE /api/runs/<id>/events ◀──┘ stderr: process log        └─ Consumer: Ditto → fair ranking → LEMON  ◀─┘
                                                                              → global merge → metrics   (Kafka or memory)
```

* **Pairs per increment** and **time budget τ** drive the producer: one batch is
  published every τ seconds (a real clock, as in the paper). If processing an increment
  takes longer than τ, the next batch waits in the queue — the UI shows "Queue (delay)"
  and flags the increment as *over τ*.
* **Explanation switch:** off = `0` (TREATS); on = choose LEMON (`1`) or SHAP (`2`), which
  maps directly to `explanation_flag` of `X_TREATS_run_gpu.py`.
* Batch slicing reproduces `X_TREATS_run_gpu.main()` exactly (the CLI receives N−1 and
  uses an inclusive `.loc` ⇒ N rows per increment).
* The worker reuses `setUpDitto`, `match_rank_streaming_explantion`,
  `merge_clusters_with_explantion`, `perform_evaluation`, etc. If you change those
  functions (e.g. the ranking sort), the interface reflects it.
* Each run is stored in `runtime/runs/<id>/` (`events.jsonl`, `run.log`, `params.json`)
  and shows up under "Previous runs" (direct link: `/#run=<id>`).

## Intentional differences from the CLI

| CLI (`X_TREATS_run_gpu.py`) | Interface |
|---|---|
| reads everything and does `sleep(τ)` **after** processing | producer sends every τ (clock); queue delay is measured |
| `total_time` = match + rank (no explanation) | matching, ranking and explanation are shown separately |
| runs the whole dataset | "Max. increments" option for short runs |
| matcher `ditto` or `gnem` | Ditto only (GNEM needs a different `transformers` version) |

**Simulation** mode (Advanced): no model is loaded and the metrics are *fake*; it exists
only to test the interface without a GPU. It is always flagged on screen.

## Notes

* One run at a time (the model occupies the GPU).
* Real runs make Ditto's `matcher.py` append a line to `log.txt` at the repo root
  (`os.system('echo ... >> log.txt')`) — existing behaviour, identical to the CLI.
* The server listens on `127.0.0.1` only and accepts only `application/json` POSTs.

## Adding your own dataset and trained model

Click **＋ Add dataset & model** under the dataset cards. Everything you upload is stored in
`web-en/uploads/datasets/<name>/` (git-ignored) — the repository itself is never modified.

| Field | Required | Notes |
|---|---|---|
| Dataset file (`.txt`) | yes | One labeled pair per line: `left entity ⇥ right entity ⇥ label`, entities as `COL <attr> VAL <value> …` (same layout as `data/er_magellan/Structured/<name>/test.txt`). UTF-8, ≥ 20 pairs, ≥ 1 match. The **first attribute** identifies the record. The browser previews the file and detects the attributes before uploading. |
| Trained model (`.pt`) | yes | A Ditto checkpoint (`{'model': state_dict, …}`) like `checkpoints/Structured/<name>/model.pt`, trained with the selected language model (`roberta` or `distilbert`). |
| Train / validation files | no | Only used for the TF-IDF index of Ditto's summarizer; the dataset file is used when omitted. |
| Match threshold | yes | Ditto's decision threshold (the built-in datasets use 0.1–0.6). |
| Sensitive attribute + keywords | yes | Defines the fairness groups: a pair joins the *first* keyword found (case-insensitive) in that attribute of either entity, otherwise group `others`. |

Uploads are streamed to disk (a 1.4 GB checkpoint takes seconds), validated server-side, and can be
removed with the ✕ on the dataset card. Uploaded datasets run with the `m-fair` ranking, with or without explanation.

**How it works without touching the pipeline.** The repository hard-codes per-dataset knowledge in four
places (Ditto's `load_model`/`configs.json`, `extractLeft/RightColumns`, `getKey`, and the group conditions in
`util.py`). `custom_runtime.py` registers the uploaded dataset **in memory, inside the worker process only**
(after importing `X_TREATS_run_gpu`); built-in datasets keep using the original code paths. Group conditions are
built only from validated identifiers and `repr()` of validated keywords, so no uploaded text is executed as code.

**Security.** A PyTorch `.pt` file is a pickle: loading it can execute code. Only upload models you trust.
The server never unpickles it — only the worker does, when you start a run — and upload only checks the file's magic bytes.

## Tests

```powershell
python web-en\tests\test_basic.py        # batching, validation, queue pacing
python web-en\tests\test_datasets.py     # upload validation, group conditions, commit flow (no GPU)
node   web-en\tests\ui_e2e.js            # drives the real UI in headless Chrome (server on :5051)
```
