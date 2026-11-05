"""Shared configuration for the X-TREATS web interface.

Everything here is read-only at runtime. Experiment defaults (datasets,
thresholds, model, k) come from X_TREATS_run_experiments.py so there is a single
source of truth; local fallbacks are used only if that module cannot be loaded.
"""
import os
import sys
import tempfile

import datasets_store as store

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, ".."))
RUNTIME_DIR = os.path.join(HERE, "runtime")
RUNS_DIR = os.path.join(RUNTIME_DIR, "runs")

SCRIPT_NAME = "X_TREATS_run_gpu.py"
DATA_ROOT = "data/er_magellan/Structured/"  # relative to REPO_ROOT, as the script expects

_FALLBACK_THRESHOLDS = {
    "Amazon-Google": 0.1,
    "Walmart-Amazon": 0.6,
    "DBLP-ACM": 0.2,
    "DBLP-GoogleScholar": 0.1,
}

# Sensitive-attribute groups per dataset (group index -> label). Index 0 is the
# "others" group. Mirrors util.default_conditions_multiple_groups / paper Table 1.
GROUPS = {
    "DBLP-GoogleScholar": {"attribute": "venue", "labels": ["others", "vldb", "sigmod", "tods"]},
    "DBLP-ACM": {"attribute": "authors", "labels": ["others", "female"]},
    "Amazon-Google": {"attribute": "manufacturer", "labels": ["others", "microsoft", "sony", "apple"]},
    "Walmart-Amazon": {"attribute": "category", "labels": ["others", "printers", "laptops", "cameras"]},
}

DOMAINS = {
    "DBLP-GoogleScholar": "Publications",
    "DBLP-ACM": "Publications",
    "Amazon-Google": "Products",
    "Walmart-Amazon": "Products",
}

ALGORITHMS = {
    0: {"id": 0, "label": "TREATS", "hint": "Baseline: fair ranking without explanation"},
    1: {"id": 1, "label": "X-TREATS · LEMON", "hint": "Per-attribute explanation + potential score"},
    2: {"id": 2, "label": "X-TREATS · SHAP", "hint": "Per-attribute explanation (no potential)"},
}


def _experiment_defaults():
    """Read defaults from the (unmodified) experiments runner."""
    if REPO_ROOT not in sys.path:
        sys.path.insert(0, REPO_ROOT)
    try:
        from X_TREATS_run_experiments import runner  # side-effect free import
        r = runner(script_path=SCRIPT_NAME, workdir=tempfile.mkdtemp(prefix="xtreats_cfg_"), dry_run=True)
        return {
            "thresholds": {k: float(v) for k, v in r.thresholds.items()},
            "lm": r.model,
            "k": int(r.k_value),
            "tau": int(r.max_candidates),
            "ranking_mode": r.fair_mode,
            "record_counts": [int(c) + 1 for c in r.record_counts],  # runner passes N-1
        }
    except Exception:
        return {
            "thresholds": dict(_FALLBACK_THRESHOLDS),
            "lm": "roberta",
            "k": 20,
            "tau": 15,
            "ranking_mode": "m-fair",
            "record_counts": [200, 400, 600],
        }


def public_config():
    d = _experiment_defaults()
    datasets = []
    for name, thr in d["thresholds"].items():
        datasets.append({
            "name": name,
            "domain": DOMAINS.get(name, ""),
            "threshold": thr,
            "available": os.path.isfile(os.path.join(REPO_ROOT, DATA_ROOT, name, "test.txt"))
            and os.path.isdir(os.path.join(REPO_ROOT, "checkpoints", "Structured", name)),
            "groups": GROUPS.get(name, {"attribute": "", "labels": ["others"]}),
            "custom": False,
        })
    for cname in store.list_names():
        meta = store.load_meta(cname)
        if not meta:
            continue
        paths = store.dataset_paths(meta)
        datasets.append({
            "name": cname,
            "domain": "Uploaded",
            "threshold": meta["threshold"],
            "available": os.path.isfile(paths["test"]) and os.path.isfile(paths["model"]),
            "groups": {"attribute": meta["sensitive_attribute"], "labels": ["others"] + meta["groups"]},
            "custom": True,
            "lm": meta["lm"],
            "lines": meta.get("lines"),
        })
    return {
        "datasets": datasets,
        "algorithms": list(ALGORITHMS.values()),
        "defaults": {
            "dataset": datasets[0]["name"] if datasets else None,
            "pairs_per_increment": d["record_counts"][0],
            "pairs_options": d["record_counts"],
            "tau": 30,  # paper default time budget; runner's 15 stays selectable
            "k": d["k"],
            "algorithm": 1,
            "lm": d["lm"],
            "ranking_mode": d["ranking_mode"],
            "max_increments": 0,
        },
        "limits": {
            "pairs": [20, 2000], "tau": [1, 300], "k": [5, 50], "max_increments": [0, 200],
        },
        "upload": {
            "lms": list(store.LMS),
            "max_bytes": {k: v[1] for k, v in store.KINDS.items()},
            "min_lines": store.MIN_LINES,
            "max_groups": store.MAX_GROUPS,
        },
    }


def validate_params(p):
    """Validate and normalise user parameters. Raises ValueError on bad input."""
    cfg = public_config()
    names = {d["name"]: d for d in cfg["datasets"]}
    out = {}
    if p.get("dataset") not in names:
        raise ValueError("Invalid dataset.")
    if not names[p["dataset"]]["available"]:
        raise ValueError("Dataset or checkpoint not found for '%s'." % p["dataset"])
    out["dataset"] = p["dataset"]
    out["threshold"] = names[p["dataset"]]["threshold"]
    out["custom"] = bool(names[p["dataset"]]["custom"])

    def _int(key, lo, hi, label):
        try:
            v = int(p.get(key))
        except (TypeError, ValueError):
            raise ValueError("%s must be an integer." % label)
        if not lo <= v <= hi:
            raise ValueError("%s must be between %d and %d." % (label, lo, hi))
        return v

    out["pairs_per_increment"] = _int("pairs_per_increment", *cfg["limits"]["pairs"], "Pairs per increment")
    out["tau"] = _int("tau", *cfg["limits"]["tau"], "Time budget (τ)")
    out["k"] = _int("k", *cfg["limits"]["k"], "Top-k")
    out["max_increments"] = _int("max_increments", *cfg["limits"]["max_increments"], "Max. increments")
    alg = _int("algorithm", 0, 2, "Algorithm")
    out["algorithm"] = alg
    out["lm"] = names[p["dataset"]].get("lm") or cfg["defaults"]["lm"]
    # The script only supports explanation with m-fair + ditto; uploaded datasets only define m-fair groups.
    out["ranking_mode"] = cfg["defaults"]["ranking_mode"] if (alg > 0 or out["custom"]) else p.get("ranking_mode", "m-fair")
    if out["ranking_mode"] not in ("m-fair", "fair-er", "none"):
        raise ValueError("Invalid ranking mode.")
    out["matcher"] = "ditto"
    out["simulate"] = bool(p.get("simulate", False))
    return out
