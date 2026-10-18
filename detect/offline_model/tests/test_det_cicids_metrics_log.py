import numpy as np
import pandas as pd
import pytest

from conftest import CLASS_NAMES, COUNTS, make_frame
import det_cicids as cicids
from det_experiments import COLUMNS, ExperimentLog
from det_metrics import binary_metrics, macro_f1, per_class_f1, unseen_detection_rate


# ---------- cleaning and encoding ----------
def test_clean_removes_bad_rows_and_duplicates_and_reports_them():
    df = make_frame(with_trouble=True)
    cleaned, report = cicids.clean(df)
    assert report["rows_in"] == len(df)
    assert report["rows_with_missing_or_infinite_values"] == 2
    assert report["duplicate_rows_removed"] == 5
    assert report["rows_out"] == len(cleaned) == len(df) - 2 - 5
    assert np.isfinite(cleaned.drop(columns=["Label"]).to_numpy()).all()


def test_keep_duplicates_option():
    cleaned, report = cicids.clean(make_frame(with_trouble=True), keep_duplicates=True)
    assert report["duplicate_rows_removed"] == 0


def test_column_names_are_stripped():
    df = make_frame().rename(columns={"f0": " f0 "})
    cleaned, _ = cicids.clean(df)
    assert "f0" in cleaned.columns


def test_string_and_numeric_labels_give_the_same_class_ids():
    _, y_text, names_text = cicids.encode(make_frame())
    _, y_num, names_num = cicids.encode(make_frame(numeric_labels=True))
    assert names_text == names_num == CLASS_NAMES
    assert (y_text == y_num).all()


def test_class_ids_follow_the_notebooks_order():
    _, y, names = cicids.encode(make_frame())
    assert names[0] == "BENIGN" and names.index("DoS") == 3 and names.index("WebAttack") == 6
    assert np.bincount(y).tolist() == [COUNTS[n] for n in CLASS_NAMES]


def test_a_new_class_name_is_added_after_the_known_ones():
    df = make_frame()
    df.loc[df["Label"] == "Bot", "Label"] = "Heartbleed"
    _, _, names = cicids.encode(df)
    assert names[-1] == "Heartbleed" and "Bot" not in names


def test_unknown_numeric_label_is_an_error():
    df = make_frame(numeric_labels=True)
    df.loc[0, "Label"] = 99
    with pytest.raises(ValueError):
        cicids.encode(df)


def test_data_without_benign_rows_is_refused():
    df = make_frame()
    with pytest.raises(ValueError):
        cicids.encode(df[df["Label"] != "BENIGN"])


# ---------- splits ----------
def test_stratified_split_keeps_every_class_in_both_parts():
    X, y, _ = cicids.encode(make_frame())
    X_train, X_test, y_train, y_test = cicids.stratified_split(X, y, seed=0)
    assert len(y_train) + len(y_test) == len(y)
    assert set(y_train) == set(y_test) == set(range(7))
    assert abs(len(y_test) / len(y) - 0.2) < 0.02


def test_split_is_repeatable_and_changes_with_the_seed():
    X, y, _ = cicids.encode(make_frame())
    a = cicids.stratified_split(X, y, seed=0)[1].index
    b = cicids.stratified_split(X, y, seed=0)[1].index
    c = cicids.stratified_split(X, y, seed=1)[1].index
    assert list(a) == list(b) and set(a) != set(c)


def test_a_class_with_one_row_cannot_be_split():
    X, y, _ = cicids.encode(make_frame())
    y = y.copy()
    y[np.where(y == 4)[0][1:]] = 0
    with pytest.raises(ValueError):
        cicids.stratified_split(X, y)


def test_inner_validation_is_carved_from_training_only():
    X, y, _ = cicids.encode(make_frame())
    X_train, _, y_train, _ = cicids.stratified_split(X, y, seed=0)
    X_fit, X_val, y_fit, y_val = cicids.inner_validation_split(X_train, y_train, seed=0)
    assert len(y_fit) + len(y_val) == len(y_train)
    assert not set(X_fit.index) & set(X_val.index)


def test_holdout_split_never_trains_on_the_hidden_attack():
    X, y, _ = cicids.encode(make_frame())
    X_train, y_train, X_test, y_test, hidden = cicids.holdout_attack_split(X, y, attack_id=2, seed=0)
    assert 2 not in set(y_train)
    assert hidden.sum() == COUNTS["BruteForce"] and (y_test[hidden] == 2).all()
    assert 2 not in set(y_test[~hidden])
    assert len(y_train) + len(y_test) - hidden.sum() == len(y) - COUNTS["BruteForce"]


# ---------- SMOTE ----------
def test_smote_lifts_small_classes_to_the_target_and_leaves_big_ones():
    X, y, _ = cicids.encode(make_frame())
    X2, y2, info = cicids.smote_balance(X, y, target=60, seed=0)
    counts = np.bincount(y2)
    assert counts[0] == COUNTS["BENIGN"] and counts[3] == COUNTS["DoS"]        # already above 60: untouched
    assert all(counts[i] == 60 for i in (1, 2, 4, 5, 6))                       # lifted
    assert info["skipped_too_small"] == {} and len(X2) == len(y2)
    assert X2.dtypes.eq("float32").all()


def test_smote_skips_a_class_that_is_too_small_to_copy():
    X, y, _ = cicids.encode(make_frame())
    keep = np.ones(len(y), dtype=bool)
    keep[np.where(y == 4)[0][4:]] = False   # leave only 4 Infiltration rows
    X2, y2, info = cicids.smote_balance(X[keep], y[keep], target=60, seed=0)
    assert info["skipped_too_small"] == {4: 4} and (y2 == 4).sum() == 4


def test_smote_with_nothing_to_do_returns_the_input():
    X, y, _ = cicids.encode(make_frame())
    X2, y2, info = cicids.smote_balance(X, y, target=5, seed=0)
    assert X2 is X and y2 is y and info["oversampled_classes"] == {}


# ---------- metrics ----------
def test_binary_metrics_by_hand():
    truth = [0, 0, 0, 0, 1, 2, 3, 3]
    guess = [0, 0, 1, 0, 1, 0, 3, 2]
    m = binary_metrics(truth, guess, benign_id=0)
    assert (m["tp"], m["fp"], m["tn"], m["fn"]) == (3, 1, 3, 1)
    assert m["precision"] == pytest.approx(0.75) and m["recall"] == pytest.approx(0.75)
    assert m["f1"] == pytest.approx(0.75) and m["false_positive_rate"] == pytest.approx(0.25)


def test_a_wrong_attack_class_still_counts_as_detected_in_the_binary_view():
    m = binary_metrics([2, 2], [3, 3], benign_id=0)
    assert m["recall"] == 1.0 and m["precision"] == 1.0


def test_impossible_ratios_are_none_not_zero():
    no_attacks = binary_metrics([0, 0], [0, 0], 0)
    assert no_attacks["recall"] is None and no_attacks["precision"] is None and no_attacks["f1"] is None
    assert no_attacks["false_positive_rate"] == 0.0
    no_benign = binary_metrics([1, 1], [1, 0], 0)
    assert no_benign["false_positive_rate"] is None


def test_macro_f1_and_per_class_f1():
    truth, guess = [0, 0, 1, 1, 2, 2], [0, 0, 1, 2, 2, 2]
    assert macro_f1(truth, guess) == pytest.approx((1.0 + 2 / 3 + 0.8) / 3)
    scores = per_class_f1(truth, guess, ["A", "B", "C"])
    assert scores["A"] == 1.0 and scores["B"] == pytest.approx(2 / 3) and scores["C"] == pytest.approx(0.8)


def test_unseen_detection_rate():
    pred = np.array([0, 3, 0, 4, 1])
    hidden = np.array([False, True, True, True, False])
    assert unseen_detection_rate(pred, hidden, benign_id=0) == pytest.approx(2 / 3)
    assert unseen_detection_rate(pred, np.zeros(5, dtype=bool), 0) is None


# ---------- experiment log ----------
def test_log_writes_a_header_once_and_one_row_per_add(tmp_path):
    log = ExperimentLog(tmp_path / "results" / "experiments.csv")
    log.add(split="stratified", model="LCCDE", precision=0.987654321, seed=0)
    log.add(split="stratified", model="XGBoost", precision=0.5, recall=None)
    lines = (tmp_path / "results" / "experiments.csv").read_text(encoding="utf-8").splitlines()
    assert lines[0].split(",") == COLUMNS and len(lines) == 3
    rows = log.rows()
    assert rows[0]["precision"] == "0.9877" and rows[1]["recall"] == "" and rows[0]["timestamp_utc"].endswith("Z")


def test_log_refuses_unknown_columns(tmp_path):
    with pytest.raises(ValueError):
        ExperimentLog(tmp_path / "e.csv").add(colour="red")


def test_reading_a_missing_log_gives_nothing(tmp_path):
    assert ExperimentLog(tmp_path / "none.csv").rows() == []
