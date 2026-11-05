"""Run-time hooks that let the *unmodified* pipeline process an uploaded dataset.

The repository hard-codes per-dataset knowledge in four places. None of those files
are edited; instead, once the worker has imported X_TREATS_run_gpu, this module
registers the uploaded dataset in memory (only for that worker process):

  1. ditto matcher.load_model      -> reads configs.json by task name and checkpoints/<task>/model.pt
  2. streaming.fairER_streaming    -> extractLeftColumns / extractRightColumns / getKey (per-dataset column names)
  3. util                          -> default_conditions_multiple_groups (sensitive groups) + number_of_groups

Built-in datasets keep using the original code paths.
"""
import os

import datasets_store as store


def install(meta):
    import matcher                      # ditto (already on sys.path via the pipeline)
    import util                         # repo root
    from streaming import fairER_streaming as fs

    name, attrs = meta["name"], meta["attributes"]
    paths = store.dataset_paths(meta)
    task = "Structured/" + name

    # 3) sensitive groups -------------------------------------------------------
    def _xt_val(v):
        # In the stream `tuple.attr` is a plain value; for the gold standard it is a
        # one-row Series whose str() would add "Name: ..., dtype: object" noise.
        if hasattr(v, "iloc"):
            v = v.iloc[0] if len(v) else ""
        return str(v).lower()

    util._xt_val = _xt_val
    util.default_conditions_multiple_groups[name] = store.build_group_condition(
        meta["sensitive_attribute"], meta["groups"])

    # 2) column naming ----------------------------------------------------------
    orig_key, orig_left, orig_right = fs.getKey, fs.extractLeftColumns, fs.extractRightColumns

    def _extract(df, side):
        parts = df[side].str.split("COL", expand=True).drop(axis=1, columns=[0])
        parts = parts.iloc[:, :len(attrs)]
        parts.columns = ["%s_%s" % (side, a) for a in attrs]
        for col in parts.columns:
            parts[col] = parts[col].str.split("VAL", expand=True)[1]
        return parts

    fs.getKey = lambda key: attrs[0] if key == name else orig_key(key)
    fs.extractLeftColumns = lambda df, data: _extract(df, "left") if data == name else orig_left(df, data)
    fs.extractRightColumns = lambda df, data: _extract(df, "right") if data == name else orig_right(df, data)

    # 1) task config + checkpoint -----------------------------------------------
    orig_load = matcher.load_model
    config = {"name": task, "task_type": "classification", "vocab": ["0", "1"],
              "trainset": paths["train"], "validset": paths["valid"], "testset": paths["test"]}

    def load_model(task_name, path, lm, use_gpu, fp16=True):
        if task_name != task:
            return orig_load(task_name, path, lm, use_gpu, fp16)
        device = "cuda" if use_gpu and matcher.torch.cuda.is_available() else "cpu"
        model = matcher.DittoModel(device=device, lm=lm)
        saved = matcher.torch.load(paths["model"], map_location=lambda storage, loc: storage)
        model.load_state_dict(saved["model"])
        model = model.to(device)
        if fp16 and "cuda" in device:
            model = matcher.amp.initialize(model, opt_level="O2")
        return config, model

    matcher.load_model = load_model
    return {"task": task, "test_path": paths["test"]}
