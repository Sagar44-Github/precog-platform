"""Loading, cleaning and splitting the CICIDS2017 sample.

Steps and the reasons for them:
  * rows with missing or infinite values are dropped (the data has a few, and models cannot use them);
  * duplicate rows are dropped BEFORE splitting, otherwise the same row can sit in both the training
    and the test set and the scores look better than they are;
  * labels become numbers in a fixed order (BENIGN first) that matches the numbers used by the
    Western OC2 Lab notebooks: 0 BENIGN, 1 Bot, 2 BruteForce, 3 DoS, 4 Infiltration, 5 PortScan, 6 WebAttack.
"""
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

LABEL_COLUMN = "Label"
BENIGN = "BENIGN"
CANONICAL_CLASSES = ["BENIGN", "Bot", "BruteForce", "DoS", "Infiltration", "PortScan", "WebAttack"]
NUMERIC_LABELS = dict(enumerate(CANONICAL_CLASSES))


def load_csv(path):
    return pd.read_csv(path)


def clean(df, keep_duplicates=False):
    """Returns (clean dataframe, report). The report says how many rows were removed and why."""
    rows_in = len(df)
    features = df.drop(columns=[LABEL_COLUMN])
    numbers = features.apply(pd.to_numeric, errors="coerce")
    bad = numbers.isna().any(axis=1) | np.isinf(numbers.to_numpy(dtype="float64", na_value=np.nan)).any(axis=1)
    cleaned = df.loc[~bad].copy()
    cleaned.columns = [str(c).strip() for c in cleaned.columns]
    after_bad = len(cleaned)
    duplicates = 0
    if not keep_duplicates:
        duplicates = int(cleaned.duplicated().sum())
        cleaned = cleaned.drop_duplicates()
    report = {
        "rows_in": rows_in,
        "rows_with_missing_or_infinite_values": int(bad.sum()),
        "duplicate_rows_removed": duplicates,
        "rows_out": len(cleaned),
    }
    assert report["rows_out"] == after_bad - duplicates
    return cleaned.reset_index(drop=True), report


def label_names(series):
    """Turn a label column into names. Numbers 0-6 use the notebooks' numbering."""
    as_text = series.astype(str).str.strip()
    if as_text.str.fullmatch(r"\d+").all():
        unknown = sorted(set(int(v) for v in as_text) - set(NUMERIC_LABELS))
        if unknown:
            raise ValueError("Unknown numeric labels: %s (known: 0-%d)" % (unknown, len(NUMERIC_LABELS) - 1))
        return as_text.map(lambda v: NUMERIC_LABELS[int(v)])
    return as_text


def encode(df):
    """Returns (X float32 DataFrame, y int array, class_names). class_names[i] is the name of class id i."""
    names = label_names(df[LABEL_COLUMN])
    present = set(names)
    if BENIGN not in present:
        raise ValueError("The data has no %s rows, so false positives cannot be measured." % BENIGN)
    class_names = [c for c in CANONICAL_CLASSES if c in present] + sorted(present - set(CANONICAL_CLASSES))
    index = {name: i for i, name in enumerate(class_names)}
    y = names.map(index).to_numpy(dtype=int)
    X = df.drop(columns=[LABEL_COLUMN]).astype("float32")
    return X, y, class_names


def _split(X, y, test_size, seed):
    counts = pd.Series(y).value_counts()
    if (counts < 2).any():
        raise ValueError("Every class needs at least 2 rows to split; too small: %s" % counts[counts < 2].to_dict())
    return train_test_split(X, y, test_size=test_size, random_state=seed, stratify=y)


def stratified_split(X, y, test_size=0.2, seed=0):
    """Random split that keeps each class's share the same in both parts."""
    return _split(X, y, test_size, seed)


def inner_validation_split(X, y, val_size=0.2, seed=0):
    """Carves a validation part out of the TRAINING data. It is used to choose each class's leader model,
    so the test data is never used for choosing anything."""
    counts = pd.Series(y).value_counts()
    if (counts < 2).any():  # a class with 1 row cannot be split: keep everything for fitting
        return X, X.iloc[0:0], y, y[0:0]
    X_fit, X_val, y_fit, y_val = _split(X, y, val_size, seed)
    return X_fit, X_val, y_fit, y_val


def holdout_attack_split(X, y, attack_id, test_size=0.2, seed=0):
    """Train WITHOUT one attack type; test on the usual 20% of the other classes plus every row of the hidden attack.
    Returns X_train, y_train, X_test, y_test, hidden_mask (True for test rows of the hidden attack)."""
    hidden = y == attack_id
    if not hidden.any():
        raise ValueError("No rows with class id %s" % attack_id)
    X_rest, y_rest = X[~hidden], y[~hidden]
    X_train, X_test_rest, y_train, y_test_rest = _split(X_rest, y_rest, test_size, seed)
    X_test = pd.concat([X_test_rest, X[hidden]])
    y_test = np.concatenate([y_test_rest, y[hidden]])
    hidden_mask = np.concatenate([np.zeros(len(y_test_rest), dtype=bool), np.ones(int(hidden.sum()), dtype=bool)])
    return X_train, y_train, X_test, y_test, hidden_mask


def smote_balance(X, y, target=1000, seed=0, k_neighbors=5):
    """Adds synthetic rows (SMOTE) to every class that has fewer than `target` rows,
    up to `target`. A class with too few rows to make neighbours from is skipped.
    Returns (X, y, info) where info says what was done."""
    from imblearn.over_sampling import SMOTE

    counts = pd.Series(y).value_counts().sort_index()
    strategy, skipped = {}, {}
    for class_id, count in counts.items():
        if count >= target:
            continue
        if count <= k_neighbors:
            skipped[int(class_id)] = int(count)
        else:
            strategy[int(class_id)] = int(target)
    info = {"target_per_class": target, "oversampled_classes": strategy, "skipped_too_small": skipped}
    if not strategy:
        return X, y, info
    sampler = SMOTE(sampling_strategy=strategy, random_state=seed, k_neighbors=k_neighbors)
    X_new, y_new = sampler.fit_resample(X, y)
    return pd.DataFrame(X_new, columns=X.columns).astype("float32"), np.asarray(y_new, dtype=int), info
