"""Trains the detection models on the CICIDS2017 sample and writes the evaluation results.

Run from inside detect/offline_model (offline environment switched on):

    python run_evaluation.py --data vendor/Intrusion-Detection-System-Using-Machine-Learning/data/CICIDS2017_sample.csv

Add --quick for a fast trial run (a smaller CatBoost). Results go to the results folder:
    experiments.csv         one row per model per run (the experiment log)
    metrics_summary.json    every number, including unseen-attack tests and each class's leader model
    detection_report.json   the short report the product shows (follows contracts/schemas/detection_report.schema.json)
    feature_columns.json    the feature names, in the order the models use
    dataset_summary.json    how many rows were removed and the class counts
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import numpy as np  # noqa: E402

import det_cicids as cicids  # noqa: E402
from det_experiments import ExperimentLog  # noqa: E402
from det_lccde import MODEL_NAMES, LccdeEnsemble  # noqa: E402
from det_metrics import binary_metrics, macro_f1, per_class_f1, unseen_detection_rate  # noqa: E402

DEFAULT_DATASET_LABEL = "CICIDS2017 (5% sample from the Western OC2 Lab repository)"
QUICK_CATBOOST_ITERATIONS = 100


def _say(message):
    print(message, flush=True)


def _fit_and_predict(X_train, y_train, X_test, args, class_names):
    """Inner validation split, SMOTE on the fitting part, fit the ensemble, predict the test rows."""
    X_fit, X_val, y_fit, y_val = cicids.inner_validation_split(X_train, y_train, seed=args.seed)
    smote_info = None
    if args.smote:
        X_fit, y_fit, smote_info = cicids.smote_balance(X_fit, y_fit, target=args.smote_target, seed=args.seed)
    ensemble = LccdeEnsemble(seed=args.seed, threads=args.threads, catboost_iterations=args.catboost_iterations)
    started = time.time()
    ensemble.fit(X_fit, y_fit, X_val, y_val)
    predictions = ensemble.predict_all(X_test)
    return ensemble, predictions, smote_info, time.time() - started, len(y_fit)


def _log_models(log, split_name, predictions, y_test, benign_id, args, n_features, train_rows, seconds, hidden_mask=None, notes=""):
    results = {}
    for model_name, predicted in predictions.items():
        metrics = binary_metrics(y_test, predicted, benign_id)
        metrics["macro_f1"] = macro_f1(y_test, predicted)
        if hidden_mask is not None:
            metrics["unseen_detection_rate"] = unseen_detection_rate(predicted, hidden_mask, benign_id)
        log.add(split=split_name, model=model_name, n_features=n_features, smote=bool(args.smote), seed=args.seed,
                train_rows=train_rows, test_rows=len(y_test), precision=metrics["precision"], recall=metrics["recall"],
                f1=metrics["f1"], false_positive_rate=metrics["false_positive_rate"], macro_f1=metrics["macro_f1"],
                unseen_detection_rate=metrics.get("unseen_detection_rate"), seconds=round(seconds, 1), notes=notes)
        results[model_name] = metrics
    return results


def build_report(summary, args, clean_report):
    main = summary["stratified"]["models"]["LCCDE"]
    for key in ("precision", "recall", "f1", "false_positive_rate"):
        if main[key] is None:
            raise ValueError("Cannot write the report: '%s' could not be calculated for the main split." % key)
    if summary.get("holdout"):
        parts = ["%s %.2f" % (name, item["models"]["LCCDE"]["unseen_detection_rate"])
                 for name, item in summary["holdout"].items() if item["models"]["LCCDE"].get("unseen_detection_rate") is not None]
        unseen = "Share of each attack type still flagged as an attack when the model was trained WITHOUT it: " + ", ".join(parts) + "."
    else:
        unseen = "The unseen-attack-type test was not run."
    notes = ("Attack = any class except BENIGN. %d rows after removing %d duplicates. %s This is lab data from a public sample, "
             "not live traffic, and it is not comparable with NIDS's live Isolation Forest detector.") % (
                 clean_report["rows_out"], clean_report["duplicate_rows_removed"], unseen)
    return {
        "model": "LCCDE ensemble (LightGBM + XGBoost + CatBoost), leaders chosen on a validation split",
        "dataset": args.dataset_label,
        "split": "Stratified random 80/20 split after removing duplicate rows (not ordered by time), seed %d" % args.seed,
        "precision": round(main["precision"], 4), "recall": round(main["recall"], 4),
        "f1": round(main["f1"], 4), "false_positive_rate": round(main["false_positive_rate"], 4),
        "notes": notes,
    }


def validate_report(report, contracts_dir):
    """Check the report against the project's contract. Needs the jsonschema library."""
    from jsonschema import Draft202012Validator

    schema_path = Path(contracts_dir) / "schemas" / "detection_report.schema.json"
    if not schema_path.is_file():
        return False
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(report))
    if errors:
        raise ValueError("detection_report.json breaks its contract: %s" % errors[0].message)
    return True


def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = ExperimentLog(out / "experiments.csv")

    _say("Reading %s" % args.data)
    cleaned, clean_report = cicids.clean(cicids.load_csv(args.data), keep_duplicates=args.keep_duplicates)
    X, y, class_names = cicids.encode(cleaned)
    benign_id = class_names.index(cicids.BENIGN)
    n_features = X.shape[1]
    counts = {name: int((y == i).sum()) for i, name in enumerate(class_names)}
    _say("%d rows after cleaning (removed %d with missing/infinite values and %d duplicates). Classes: %s" % (
        clean_report["rows_out"], clean_report["rows_with_missing_or_infinite_values"],
        clean_report["duplicate_rows_removed"], counts))
    (out / "feature_columns.json").write_text(json.dumps(list(X.columns), indent=2) + "\n", encoding="utf-8")
    (out / "dataset_summary.json").write_text(json.dumps({"cleaning": clean_report, "class_counts": counts}, indent=2) + "\n", encoding="utf-8")

    summary = {"created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "seed": args.seed,
               "smote": bool(args.smote), "catboost_iterations": args.catboost_iterations, "classes": class_names}

    # ---- main split ----
    _say("Main split: stratified 80/20 ...")
    X_train, X_test, y_train, y_test = cicids.stratified_split(X, y, seed=args.seed)
    ensemble, predictions, smote_info, seconds, fit_rows = _fit_and_predict(X_train, y_train, X_test, args, class_names)
    models = _log_models(log, "stratified_80_20", predictions, y_test, benign_id, args, n_features, fit_rows, seconds)
    leaders = {class_names[int(ensemble.classes_[i])]: MODEL_NAMES[int(m)] for i, m in enumerate(ensemble.leaders)}
    summary["stratified"] = {
        "train_rows_after_smote": fit_rows, "test_rows": len(y_test), "smote": smote_info, "models": models,
        "lccde_per_class_f1": per_class_f1(y_test, predictions["LCCDE"], class_names), "leaders": leaders, "seconds": round(seconds, 1)}
    main = models["LCCDE"]
    _say("  LCCDE: precision %.4f, recall %.4f, F1 %.4f, false-positive rate %.4f" % (
        main["precision"], main["recall"], main["f1"], main["false_positive_rate"]))

    # ---- unseen attack types ----
    if not args.skip_holdout:
        summary["holdout"] = {}
        for attack_id, attack_name in enumerate(class_names):
            if attack_id == benign_id:
                continue
            _say("Unseen-attack test: training without %s ..." % attack_name)
            X_tr, y_tr, X_te, y_te, hidden = cicids.holdout_attack_split(X, y, attack_id, seed=args.seed)
            _, preds, _, secs, rows = _fit_and_predict(X_tr, y_tr, X_te, args, class_names)
            results = _log_models(log, "holdout:%s" % attack_name, preds, y_te, benign_id, args, n_features, rows, secs,
                                  hidden_mask=hidden, notes="trained without %s" % attack_name)
            summary["holdout"][attack_name] = {"hidden_rows": int(hidden.sum()), "models": results, "seconds": round(secs, 1)}
            _say("  share of %s still flagged: %.2f" % (attack_name, results["LCCDE"]["unseen_detection_rate"]))

    (out / "metrics_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    report = build_report(summary, args, clean_report)
    checked = validate_report(report, args.contracts_dir)
    (out / "detection_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    _say("Wrote results to %s%s" % (out, " (report checked against its contract)" if checked else " (contract file not found, report not checked)"))
    return summary


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Train and evaluate the CICIDS2017 detection models.")
    parser.add_argument("--data", required=True, help="path to the CICIDS2017 CSV file")
    parser.add_argument("--out", default=str(HERE / "results"), help="folder for the results (default: results)")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--no-smote", dest="smote", action="store_false", help="do not add synthetic rows for small classes")
    parser.add_argument("--smote-target", type=int, default=1000)
    parser.add_argument("--catboost-iterations", type=int, default=1000)
    parser.add_argument("--quick", action="store_true", help="fast trial run: CatBoost uses %d iterations" % QUICK_CATBOOST_ITERATIONS)
    parser.add_argument("--threads", type=int, default=0, help="CPU threads to use (0 = all)")
    parser.add_argument("--skip-holdout", action="store_true", help="skip the unseen-attack-type tests (much faster)")
    parser.add_argument("--keep-duplicates", action="store_true")
    parser.add_argument("--dataset-label", default=DEFAULT_DATASET_LABEL)
    parser.add_argument("--contracts-dir", default=str(HERE.parents[1] / "contracts"))
    args = parser.parse_args(argv)
    if args.quick:
        args.catboost_iterations = QUICK_CATBOOST_ITERATIONS
    return args


if __name__ == "__main__":
    run(parse_args())
