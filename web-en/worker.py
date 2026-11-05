"""X-TREATS worker: runs one experiment in its own process and reports JSON events.

Usage:  python web-en/worker.py <params.json> <run_id>

It *imports* the unmodified X_TREATS_run_gpu.py and reuses its functions
(setUpDitto, match_rank_streaming_explantion, merge_clusters_with_explantion,
perform_evaluation, ...). Only the outer loop is re-implemented so that
micro-batches can arrive through Kafka, paced by the time budget (tau), instead
of the script's read-everything-then-sleep loop. The slicing arithmetic mirrors
X_TREATS_run_gpu.main() so batch contents are identical to a CLI run.

Protocol: one JSON object per line on the real stdout. Everything the imported
code prints (it is chatty) is redirected to stderr and shown as the run log.
"""
import io
import json
import os
import random
import sys
import threading
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config  # noqa: E402
import kafka_bus  # noqa: E402
import datasets_store as store  # noqa: E402
import custom_runtime  # noqa: E402

# --- event channel -----------------------------------------------------------
_events = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
sys.stdout = sys.stderr  # imported code prints to the log, not the event channel


def emit(ev):
    _events.write(json.dumps(ev, ensure_ascii=False) + "\n")
    _events.flush()


def _f(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


# --- shared helpers ----------------------------------------------------------
def build_batches(rows, pairs_per_increment, max_increments):
    """Same arithmetic as X_TREATS_run_gpu.main(): the script receives N-1 as its
    batch argument and slices with an inclusive .loc, so N rows per increment."""
    n_batches = pairs_per_increment - 1
    window = n_batches
    init = 0
    pair_size = len(rows) - 1
    batches = []
    while init < pair_size:
        end = min(n_batches, pair_size)
        chunk = rows[init:end + 1]
        batches.append({"pairs": [r.split("\t")[:2] for r in chunk], "reference_end": end})
        init = n_batches + 1
        n_batches = init + window
        if max_increments and len(batches) >= max_increments:
            break
    return batches


def _gold_key(line):
    left = line.split("\t")[0].split("VAL")[1].split("COL")[0].strip()
    right = line.split("\t")[1].split("VAL")[1].split("COL")[0].strip()
    return left, right


def gold_index(labed_file):
    gold = {}
    for line in labed_file:
        try:
            gold[_gold_key(line)] = line[-1] == "1"
        except IndexError:
            continue
    return gold


def top_rows(incremental_clusters, new_keys, gold):
    rows = []
    for rank, c in enumerate(incremental_clusters, 1):
        left, right = str(c[0]).strip(), str(c[1]).strip()
        rows.append({
            "rank": rank,
            "left": left,
            "right": right,
            "sim": _f(c[2]),
            "group": int(c[3]),
            "es": _f(c[4]) if len(c) > 4 else None,
            "new": (c[0], c[1]) in new_keys,
            "correct": gold.get((left, right)),
        })
    return rows


# --- real run ----------------------------------------------------------------
def run_real(p, bus, stop):
    os.chdir(config.REPO_ROOT)
    sys.path.insert(0, config.REPO_ROOT)
    emit({"type": "status", "state": "loading", "message": "Importing X_TREATS_run_gpu and loading Ditto…"})
    import X_TREATS_run_gpu as xt  # heavy: torch, ditto, GNEM, lemon

    task, flag, k, lm = p["dataset"], p["algorithm"], p["k"], p["lm"]
    ranking_mode = p["ranking_mode"]
    base = config.DATA_ROOT + task + "/test.txt"
    if p.get("custom"):  # uploaded dataset: register it in this process (no repo files are edited)
        base = custom_runtime.install(store.load_meta(task))["test_path"]
    with open(base, encoding="utf8") as fh:
        labed_file = [line.rstrip() for line in fh]
    df = xt.open_csv(base)
    rows = df[0].tolist()
    gold = gold_index(labed_file)

    cfg, model, threshold, summarizer, dk_injector = xt.setUpDitto(
        task="Structured/" + task, lm=lm, checkpoint_path="checkpoints/", threshold=p["threshold"])

    batches = build_batches(rows, p["pairs_per_increment"], p["max_increments"])
    emit({"type": "run_started", "total_pairs": len(rows), "n_increments": len(batches),
          "threshold": _f(threshold), "simulated": False})

    producer = kafka_bus.Producer(bus, batches, p["tau"], stop)
    producer.start()

    results = {"top-5": [], "top-10": [], "top-15": [], "top-20": [], "time_to_match": [],
               "time_to_rank": [], "time_to_explain": [], "total_time": [], "PPVP": [],
               "TPRP": [], "Bias": [], "ES": [], "Explanation": []}
    incremental_clusters, next_protected, pairs_processed = [], True, 0

    while not stop.is_set():
        msg = bus.poll(1.0)
        if msg is None:
            continue
        if msg.get("eof"):
            break
        received = time.time()
        lag = received - msg["sent_at"]
        pairs = msg["pairs"]
        reference = labed_file[0:msg["reference_end"]]
        emit({"type": "increment_started", "index": msg["index"], "pairs": len(pairs), "lag_s": lag})

        current_explanation = []
        if flag > 0:
            clusters, _, _, next_protected, t_match, t_rank, exp, t_explain = xt.match_rank_streaming_explantion(
                task, pairs, next_protected, cfg, model, threshold, summarizer, dk_injector, lm, k,
                ranking_mode, flag, [], incremental_clusters)
            for item in exp.values():
                xt.extract_attribute_tuples(item.attributions)
            current_explanation = xt.get_attribute_averages()
            clusters = xt.add_explanation_info(clusters, exp)
        else:
            clusters, _, _, next_protected, t_match, t_rank = xt.match_rank_streaming(
                task, pairs, next_protected, cfg, model, threshold, summarizer, dk_injector, lm, k,
                ranking_mode, [])
            t_explain = 0.0
        new_keys = {(c[0], c[1]) for c in clusters}

        if ranking_mode == "none":
            incremental_clusters.extend(clusters)
            incremental_clusters.sort(key=xt.sortBySimilarity, reverse=True)
            incremental_clusters = incremental_clusters[0:k]
        elif flag > 0:
            incremental_clusters = xt.merge_clusters_with_explantion(clusters, incremental_clusters, k, ranking_mode)
        else:
            incremental_clusters = xt.merge_clusters(clusters, incremental_clusters, k, ranking_mode)

        results["time_to_match"].append(t_match)
        results["time_to_rank"].append(t_rank)
        results["total_time"].append(t_match + t_rank)
        if flag > 0:
            results["time_to_explain"].append(t_explain)
            results["ES"].append(xt.compute_EFS_average(incremental_clusters))
        xt.perform_evaluation(task, incremental_clusters, reference, results, ranking_mode)

        pairs_processed += len(pairs)
        done = time.time()
        processing = t_match + t_rank + t_explain
        emit({
            "type": "increment",
            "index": msg["index"],
            "pairs": len(pairs),
            "pairs_processed": pairs_processed,
            "timings": {"match": t_match, "rank": t_rank, "explain": t_explain,
                        "processing": processing, "tau": p["tau"],
                        "lag": lag, "latency": done - msg["sent_at"]},
            "over_budget": processing > p["tau"],
            "metrics": {
                "p5": results["top-5"][-1], "p10": results["top-10"][-1],
                "p15": results["top-15"][-1], "p20": results["top-20"][-1],
                "bias": _f(results["Bias"][-1]), "ppvp": _f(results["PPVP"][-1]),
                "tprp": _f(results["TPRP"][-1]),
                "es": _f(results["ES"][-1]) if flag > 0 else None,
            },
            "top": top_rows(incremental_clusters, new_keys, gold),
            "attributes": [{"key": a, "weight": _f(w), "potential": _f(pt)} for a, w, pt in current_explanation],
        })


# --- simulated run (UI development / demo; never confused with a real run) ---
def run_simulated(p, bus, stop):
    rnd = random.Random(7)
    base = os.path.join(config.REPO_ROOT, config.DATA_ROOT, p["dataset"], "test.txt")
    if p.get("custom"):
        base = store.dataset_paths(store.load_meta(p["dataset"]))["test"]
    with open(base, encoding="utf8") as fh:
        rows = [l.rstrip() for l in fh]
    gold = gold_index(rows)
    batches = build_batches(rows, p["pairs_per_increment"], p["max_increments"])
    emit({"type": "status", "state": "loading", "message": "SIMULATION mode: no model is loaded."})
    time.sleep(1.0)
    emit({"type": "run_started", "total_pairs": len(rows), "n_increments": len(batches),
          "threshold": p["threshold"], "simulated": True})
    kafka_bus.Producer(bus, batches, p["tau"], stop).start()
    n_groups = (len(store.load_meta(p["dataset"])["groups"]) + 1) if p.get("custom") else len(config.GROUPS[p["dataset"]]["labels"])
    attrs = [("left.title", .35), ("right.title", .33), ("left.manufacturer", .12), ("right.manufacturer", .1),
             ("left.price", .03), ("right.price", .02)]
    pool, processed = [], 0
    while not stop.is_set():
        msg = bus.poll(1.0)
        if msg is None:
            continue
        if msg.get("eof"):
            break
        lag = time.time() - msg["sent_at"]
        emit({"type": "increment_started", "index": msg["index"], "pairs": len(msg["pairs"]), "lag_s": lag})
        t_match, t_rank = rnd.uniform(.7, 1.3), rnd.uniform(.01, .04)
        t_exp = rnd.uniform(9, 23) if p["algorithm"] else 0.0
        time.sleep(min(2.5, (t_match + t_exp) / 8))  # compressed wall-clock
        fresh = []
        for left, right in msg["pairs"][:60]:
            try:
                l = left.split("VAL")[1].split("COL")[0].strip()
                r = right.split("VAL")[1].split("COL")[0].strip()
            except IndexError:
                continue
            sim = rnd.uniform(.85, .9999)
            es = rnd.uniform(.05, .3) if p["algorithm"] else None
            fresh.append((l, r, sim, rnd.randrange(n_groups), es))
        pool = sorted(pool + fresh, key=lambda c: -c[2])[:p["k"]]
        new_keys = {(c[0], c[1]) for c in fresh}
        processed += len(msg["pairs"])
        i = msg["index"]
        proc = t_match + t_rank + t_exp
        emit({
            "type": "increment", "index": i, "pairs": len(msg["pairs"]), "pairs_processed": processed,
            "timings": {"match": t_match, "rank": t_rank, "explain": t_exp, "processing": proc,
                        "tau": p["tau"], "lag": lag, "latency": lag + proc},
            "over_budget": proc > p["tau"],
            "metrics": {"p5": 1.0, "p10": 1.0, "p15": round(1 - rnd.random() * .1, 2),
                        "p20": round(1 - rnd.random() * .15, 2),
                        "bias": max(0.0, round(.6 / i + rnd.uniform(0, .05), 3)),
                        "ppvp": round(rnd.uniform(0, .1), 3), "tprp": round(rnd.uniform(0, .15), 3),
                        "es": round(.1 + .02 * min(i, 6) + rnd.uniform(0, .02), 3) if p["algorithm"] else None},
            "top": top_rows(pool, new_keys, gold),
            "attributes": [{"key": a, "weight": w * rnd.uniform(.8, 1.2), "potential": rnd.uniform(-.1, .2)}
                           for a, w in attrs] if p["algorithm"] else [],
        })


def main():
    params_path, run_id = sys.argv[1], sys.argv[2]
    with open(params_path, encoding="utf-8") as fh:
        p = json.load(fh)
    stop = threading.Event()
    bus = None
    try:
        bus, note = kafka_bus.open_bus(run_id, prefer_kafka=True)
        emit({"type": "transport", "name": bus.name, "note": note,
              "topic": getattr(bus, "topic", None)})
        (run_simulated if p.get("simulate") else run_real)(p, bus, stop)
        emit({"type": "done"})
    except BaseException as e:  # report, then exit non-zero
        emit({"type": "error", "message": "%s: %s" % (type(e).__name__, e),
              "traceback": traceback.format_exc()})
        sys.exit(1)
    finally:
        stop.set()
        if bus is not None:
            bus.close()


if __name__ == "__main__":
    main()
