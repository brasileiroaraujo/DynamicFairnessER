"""Storage and validation for user-uploaded datasets and trained Ditto models.

Everything lives under web-en/uploads/:

    uploads/datasets/<name>/{meta.json, test.txt, [train.txt], [valid.txt], model.pt}
    uploads/.staging/<token>/...     (partial uploads, removed on commit/expiry)

Pure Python (no torch / pandas) so it can be imported by the web server and tested
without a GPU. The dataset format is the Ditto/Magellan one used by
data/er_magellan/Structured/<name>/test.txt.
"""
import json
import os
import re
import shutil
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
UPLOADS_DIR = os.path.join(HERE, "uploads")
DATASETS_DIR = os.path.join(UPLOADS_DIR, "datasets")
STAGING_DIR = os.path.join(UPLOADS_DIR, ".staging")

KINDS = {  # kind -> (final file name, max bytes, required)
    "test": ("test.txt", 300 * 1024 ** 2, True),
    "train": ("train.txt", 300 * 1024 ** 2, False),
    "valid": ("valid.txt", 300 * 1024 ** 2, False),
    "model": ("model.pt", 6 * 1024 ** 3, True),
}
LMS = ("roberta", "distilbert")  # the only language models Ditto's loader knows
NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{1,39}$")
ATTR_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
KEYWORD_RE = re.compile(r"^[\w\- .&+/]{1,40}$", re.UNICODE)
MIN_LINES, MAX_GROUPS = 20, 6
STAGING_TTL = 24 * 3600


class ValidationError(ValueError):
    pass


# ───────────────────────── names ─────────────────────────
def reserved_names(repo_root):
    root = os.path.join(repo_root, "data", "er_magellan", "Structured")
    names = set(os.listdir(root)) if os.path.isdir(root) else set()
    return {n.lower() for n in names} | {"structured"}


def validate_name(name, repo_root):
    if not isinstance(name, str) or not NAME_RE.match(name):
        raise ValidationError("Name must start with a letter and use only letters, digits, '-' or '_' (2–40 characters).")
    if name.lower() in reserved_names(repo_root):
        raise ValidationError("'%s' is already a built-in dataset name." % name)
    if name.lower() in {n.lower() for n in list_names()}:
        raise ValidationError("A dataset named '%s' already exists." % name)


def list_names():
    if not os.path.isdir(DATASETS_DIR):
        return []
    return sorted(d for d in os.listdir(DATASETS_DIR) if os.path.isfile(os.path.join(DATASETS_DIR, d, "meta.json")))


# ───────────────────────── file format ─────────────────────────
def parse_side(side):
    """'COL a VAL x COL b VAL y' -> [('a','x'),('b','y')]  (same naive split the pipeline uses)."""
    attrs = []
    for chunk in side.split("COL")[1:]:
        parts = chunk.split("VAL")
        if len(parts) != 2:
            raise ValidationError("an entity contains the words 'COL' or 'VAL' inside a value (not supported by the pipeline)")
        attrs.append((parts[0].strip(), parts[1].strip()))
    return attrs


def validate_dataset_file(path, expected_attrs=None, require_positives=True):
    """Validate a labeled pairs file; return a summary dict. Raises ValidationError.

    Also rewrites the file normalised (LF line endings, no blank lines, rstripped).
    """
    attrs, lines, positives, errors = None, 0, 0, []
    tmp = path + ".norm"

    def fail(n, msg):
        errors.append("line %d: %s" % (n, msg))

    try:
        with open(path, "r", encoding="utf-8", newline=None) as src, open(tmp, "w", encoding="utf-8", newline="\n") as dst:
            for n, raw in enumerate(src, 1):
                line = raw.rstrip()
                if not line:
                    continue
                fields = line.split("\t")
                if len(fields) != 3:
                    fail(n, "expected 3 tab-separated fields (left entity, right entity, label), found %d" % len(fields))
                elif fields[2].strip() not in ("0", "1"):
                    fail(n, "label must be 0 or 1, found '%s'" % fields[2].strip()[:10])
                else:
                    try:
                        left, right = parse_side(fields[0]), parse_side(fields[1])
                        l_names, r_names = [a for a, _ in left], [a for a, _ in right]
                        if not l_names:
                            fail(n, "entities must look like 'COL <attribute> VAL <value> ...'")
                        elif l_names != r_names:
                            fail(n, "left and right entities must have the same attributes in the same order")
                        else:
                            if attrs is None:
                                attrs = l_names
                                bad = [a for a in attrs if not ATTR_RE.match(a)]
                                if bad:
                                    fail(n, "invalid attribute name(s) %s: use letters, digits and '_' only (no spaces)" % bad)
                                if len(set(attrs)) != len(attrs):
                                    fail(n, "duplicated attribute names")
                            elif l_names != attrs:
                                fail(n, "attributes differ from the first line (%s)" % ", ".join(attrs))
                            if not left[0][1] or not right[0][1]:
                                fail(n, "the first attribute (record identifier) cannot be empty")
                    except ValidationError as e:
                        fail(n, str(e))
                lines += 1
                positives += 1 if fields[-1].strip() == "1" else 0
                dst.write(line + "\n")
                if len(errors) >= 5:
                    break
    except UnicodeDecodeError:
        _rm(tmp)
        raise ValidationError("The file is not valid UTF-8 text.")
    if errors:
        _rm(tmp)
        raise ValidationError("; ".join(errors[:5]))
    if lines < MIN_LINES:
        _rm(tmp)
        raise ValidationError("At least %d labeled pairs are required (found %d)." % (MIN_LINES, lines))
    if require_positives and positives == 0:
        _rm(tmp)
        raise ValidationError("The file has no matching pairs (label 1); nothing could be resolved.")
    if expected_attrs is not None and attrs != expected_attrs:
        _rm(tmp)
        raise ValidationError("Attributes (%s) differ from the test file (%s)." % (", ".join(attrs), ", ".join(expected_attrs)))
    os.replace(tmp, path)
    return {"lines": lines, "positives": positives, "attributes": attrs}


def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass


def check_model_file(path):
    """Cheap, *safe* sanity check (no unpickling): torch .pt files are zip archives or raw pickles."""
    with open(path, "rb") as fh:
        head = fh.read(4)
    if not (head[:2] == b"PK" or head[:1] == b"\x80"):
        raise ValidationError("The model file does not look like a PyTorch checkpoint (.pt).")


# ───────────────────────── groups ─────────────────────────
def parse_keywords(raw):
    if isinstance(raw, str):
        raw = raw.split(",")
    out, seen = [], set()
    for kw in raw or []:
        kw = str(kw).strip().lower()
        if not kw:
            continue
        if not KEYWORD_RE.match(kw) or " if " in " %s " % kw:
            raise ValidationError("Invalid group keyword '%s' (letters, digits, spaces and - . & + / only; max 40 characters)." % kw[:40])
        if kw not in seen:
            seen.add(kw)
            out.append(kw)
    if not out:
        raise ValidationError("Provide at least one group keyword (e.g. 'microsoft, sony').")
    if len(out) > MAX_GROUPS:
        raise ValidationError("At most %d groups are supported." % MAX_GROUPS)
    return out


def build_group_condition(attribute, keywords):
    """Expression eval'd by util.pair_is_protected_by_group (group 0 = others).

    Built only from a validated attribute identifier and repr() of validated keywords,
    so no user text is ever executed as code. Uses the helper `_xt_val`, which
    custom_runtime injects into the util module.
    """
    if not ATTR_RE.match(attribute):
        raise ValidationError("Invalid sensitive attribute.")
    parts = []
    for i, kw in enumerate(keywords, 1):
        lit = repr(kw)
        parts.append("%d if (%s in _xt_val(tuple.left_%s)) or (%s in _xt_val(tuple.right_%s))" % (i, lit, attribute, lit, attribute))
    return " else ".join(parts) + " else 0"


# ───────────────────────── staging / commit ─────────────────────────
def new_staging():
    os.makedirs(STAGING_DIR, exist_ok=True)
    purge_staging()
    token = uuid.uuid4().hex
    os.makedirs(os.path.join(STAGING_DIR, token))
    return token


def staging_path(token, kind=None):
    if not re.fullmatch(r"[0-9a-f]{32}", token or ""):
        raise ValidationError("Invalid upload token.")
    base = os.path.join(STAGING_DIR, token)
    if not os.path.isdir(base):
        raise ValidationError("Upload session not found or expired.")
    return base if kind is None else os.path.join(base, KINDS[kind][0])


def purge_staging(ttl=STAGING_TTL):
    if not os.path.isdir(STAGING_DIR):
        return
    now = time.time()
    for d in os.listdir(STAGING_DIR):
        p = os.path.join(STAGING_DIR, d)
        if os.path.isdir(p) and now - os.path.getmtime(p) > ttl:
            shutil.rmtree(p, ignore_errors=True)


def commit(token, params, repo_root):
    """Validate staged files + metadata and publish the dataset. Returns the meta dict."""
    base = staging_path(token)
    name = params.get("name")
    validate_name(name, repo_root)
    lm = params.get("lm", "roberta")
    if lm not in LMS:
        raise ValidationError("Language model must be one of: %s." % ", ".join(LMS))
    try:
        threshold = float(params.get("threshold"))
    except (TypeError, ValueError):
        raise ValidationError("Threshold must be a number.")
    if not 0.01 <= threshold <= 0.99:
        raise ValidationError("Threshold must be between 0.01 and 0.99.")

    for kind, (fname, _, required) in KINDS.items():
        if required and not os.path.isfile(os.path.join(base, fname)):
            raise ValidationError("Missing required file: %s." % fname)

    summary = validate_dataset_file(os.path.join(base, "test.txt"))
    attrs = summary["attributes"]
    for kind in ("train", "valid"):
        p = os.path.join(base, KINDS[kind][0])
        if os.path.isfile(p):
            try:
                validate_dataset_file(p, expected_attrs=attrs, require_positives=False)
            except ValidationError as e:
                raise ValidationError("%s: %s" % (KINDS[kind][0], e))
    check_model_file(os.path.join(base, "model.pt"))

    sens = params.get("sensitive_attribute")
    if sens not in attrs:
        raise ValidationError("Sensitive attribute must be one of: %s." % ", ".join(attrs))
    keywords = parse_keywords(params.get("groups"))

    meta = {
        "name": name, "created_at": time.time(), "lm": lm, "threshold": threshold,
        "attributes": attrs, "key_attribute": attrs[0],
        "sensitive_attribute": sens, "groups": keywords,
        "lines": summary["lines"], "positives": summary["positives"],
        "files": {k: os.path.isfile(os.path.join(base, KINDS[k][0])) for k in KINDS},
        "model_bytes": os.path.getsize(os.path.join(base, "model.pt")),
    }
    final = os.path.join(DATASETS_DIR, name)
    os.makedirs(DATASETS_DIR, exist_ok=True)
    os.replace(base, final)  # same filesystem: atomic move, no copy of the (large) model
    with open(os.path.join(final, "meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    return meta


def load_meta(name):
    if not name or not NAME_RE.match(name):
        return None
    p = os.path.join(DATASETS_DIR, name, "meta.json")
    if not os.path.isfile(p):
        return None
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def dataset_paths(meta):
    d = os.path.join(DATASETS_DIR, meta["name"])
    test = os.path.join(d, "test.txt")
    train, valid = os.path.join(d, "train.txt"), os.path.join(d, "valid.txt")
    return {
        "dir": d, "test": test, "model": os.path.join(d, "model.pt"),
        # the Summarizer's TF-IDF index reads all three; fall back to the test file
        "train": train if os.path.isfile(train) else test,
        "valid": valid if os.path.isfile(valid) else test,
    }


def delete(name):
    meta = load_meta(name)
    if not meta:
        raise ValidationError("Dataset not found.")
    shutil.rmtree(os.path.join(DATASETS_DIR, name))
