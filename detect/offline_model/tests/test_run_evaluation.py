import json
import os
from pathlib import Path

import pytest

import run_evaluation
from conftest import make_frame

REPO = Path(__file__).resolve().parents[3]
REAL_SAMPLE = Path(__file__).resolve().parents[1] / "vendor" / "Intrusion-Detection-System-Using-Machine-Learning" / "data" / "CICIDS2017_sample.csv"


def run(csv_path, out, **extra):
    argv = ["--data", str(csv_path), "--out", str(out), "--threads", "1", "--catboost-iterations", "20",
            "--smote-target", "40", "--contracts-dir", str(REPO / "contracts")]
    for key, value in extra.items():
        argv += ["--" + key.replace("_", "-")] + ([] if value is True else [str(value)])
    return run_evaluation.run(run_evaluation.parse_args(argv))


def test_full_run_on_made_up_data_writes_every_result_file(csv_path, tmp_path):
    out = tmp_path / "results"
    summary = run(csv_path, out)
    for name in ("experiments.csv", "metrics_summary.json", "detection_report.json", "feature_columns.json", "dataset_summary.json"):
        assert (out / name).is_file(), name
    assert len(json.loads((out / "feature_columns.json").read_text())) == 10
    assert set(summary["holdout"]) == {"Bot", "BruteForce", "DoS", "Infiltration", "PortScan", "WebAttack"}
    assert summary["stratified"]["models"]["LCCDE"]["f1"] > 0.9
    assert set(summary["stratified"]["leaders"]) == {"BENIGN", "Bot", "BruteForce", "DoS", "Infiltration", "PortScan", "WebAttack"}


def test_experiment_log_has_a_row_per_model_per_split(csv_path, tmp_path):
    run(csv_path, tmp_path / "r")
    lines = (tmp_path / "r" / "experiments.csv").read_text().splitlines()
    assert len(lines) == 1 + 4 * (1 + 6)   # header + 4 models x (main split + 6 hidden attacks)
    assert any("holdout:BruteForce" in line for line in lines)


def test_report_follows_its_contract_and_is_honest_about_what_it_is(csv_path, tmp_path):
    run(csv_path, tmp_path / "r")
    report = json.loads((tmp_path / "r" / "detection_report.json").read_text())
    assert set(report) == {"model", "dataset", "split", "precision", "recall", "f1", "false_positive_rate", "notes"}
    assert "validation split" in report["model"] and "not ordered by time" in report["split"]
    assert "WITHOUT it" in report["notes"] and "not live traffic" in report["notes"] and "duplicates" in report["notes"]


def test_skip_holdout_is_faster_and_says_so_in_the_report(csv_path, tmp_path):
    summary = run(csv_path, tmp_path / "r", skip_holdout=True)
    assert "holdout" not in summary
    assert "was not run" in json.loads((tmp_path / "r" / "detection_report.json").read_text())["notes"]
    assert len((tmp_path / "r" / "experiments.csv").read_text().splitlines()) == 1 + 4


def test_running_twice_appends_to_the_log_and_is_repeatable(csv_path, tmp_path):
    first = run(csv_path, tmp_path / "r", skip_holdout=True)
    second = run(csv_path, tmp_path / "r", skip_holdout=True)
    assert first["stratified"]["models"]["LCCDE"]["precision"] == second["stratified"]["models"]["LCCDE"]["precision"]
    assert len((tmp_path / "r" / "experiments.csv").read_text().splitlines()) == 1 + 8


def test_no_smote_option(csv_path, tmp_path):
    summary = run(csv_path, tmp_path / "r", skip_holdout=True, no_smote=True)
    assert summary["stratified"]["smote"] is None and summary["smote"] is False


def test_dirty_data_is_cleaned_and_reported(tmp_path):
    path = tmp_path / "dirty.csv"
    make_frame(with_trouble=True).to_csv(path, index=False)
    summary = run(path, tmp_path / "r", skip_holdout=True)
    cleaning = json.loads((tmp_path / "r" / "dataset_summary.json").read_text())["cleaning"]
    assert cleaning["duplicate_rows_removed"] == 5 and cleaning["rows_with_missing_or_infinite_values"] == 2
    assert "after removing 5 duplicates" in json.loads((tmp_path / "r" / "detection_report.json").read_text())["notes"]


def test_quick_flag_shrinks_catboost():
    args = run_evaluation.parse_args(["--data", "x.csv", "--quick"])
    assert args.catboost_iterations == run_evaluation.QUICK_CATBOOST_ITERATIONS
    assert run_evaluation.parse_args(["--data", "x.csv"]).catboost_iterations == 1000


def test_a_report_that_cannot_be_calculated_is_refused():
    summary = {"stratified": {"models": {"LCCDE": {"precision": None, "recall": 1.0, "f1": None, "false_positive_rate": 0.0}}}}
    args = run_evaluation.parse_args(["--data", "x.csv"])
    with pytest.raises(ValueError):
        run_evaluation.build_report(summary, args, {"rows_out": 1, "duplicate_rows_removed": 0})


def test_a_report_that_breaks_the_contract_is_refused():
    with pytest.raises(ValueError):
        run_evaluation.validate_report({"model": "x"}, REPO / "contracts")


@pytest.mark.skipif(not REAL_SAMPLE.is_file() or not os.environ.get("RUN_REAL_DATA"),
                    reason="needs the downloaded sample and RUN_REAL_DATA=1 (takes minutes)")
def test_real_sample_stratified_run(tmp_path):
    summary = run_evaluation.run(run_evaluation.parse_args([
        "--data", str(REAL_SAMPLE), "--out", str(tmp_path), "--quick", "--skip-holdout", "--contracts-dir", str(REPO / "contracts")]))
    assert summary["stratified"]["models"]["LCCDE"]["f1"] > 0.95
