# detect/offline_model — DETECT's offline CICIDS2017 work

Runs in its **own Python environment** (`.venv` inside this folder). The backend never imports anything from here.

| File | What it does |
|---|---|
| `det_cicids.py` | Loads, cleans and splits the CICIDS2017 sample; SMOTE for small classes |
| `det_lccde.py` | The LCCDE ensemble (LightGBM + XGBoost + CatBoost) |
| `det_metrics.py` | Precision, recall, F1, false-positive rate, unseen-attack rate |
| `det_experiments.py` | The experiment log (`results/experiments.csv`) |
| `run_evaluation.py` | Does everything and writes `results/` |
| `requirements.txt` | The libraries and their tested versions |
| `tests/` | Automatic tests (`pytest` from inside this folder) |
| `results/` | `experiments.csv`, `metrics_summary.json`, `detection_report.json` (the one the product shows), `feature_columns.json`, `dataset_summary.json` |
| `vendor/` | A clone of the Western OC2 Lab repository (MIT licence) for its data. Not committed |

Idea and data: Western OC2 Lab, https://github.com/Western-OC2-Lab/Intrusion-Detection-System-Using-Machine-Learning (MIT licence).
