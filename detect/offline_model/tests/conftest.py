"""Test set-up for the offline model (run from detect/offline_model with plain 'pytest')."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

CLASS_NAMES = ["BENIGN", "Bot", "BruteForce", "DoS", "Infiltration", "PortScan", "WebAttack"]
COUNTS = {"BENIGN": 120, "Bot": 40, "BruteForce": 36, "DoS": 80, "Infiltration": 14, "PortScan": 30, "WebAttack": 30}


def make_frame(seed=0, with_trouble=False, numeric_labels=False):
    """A small made-up dataset: 7 classes, 10 features, each class in its own corner."""
    rng = np.random.default_rng(seed)
    frames = []
    for class_id, name in enumerate(CLASS_NAMES):
        centre = rng.normal(0, 6, size=10)
        data = rng.normal(centre, 1.0, size=(COUNTS[name], 10))
        frame = pd.DataFrame(data, columns=["f%d" % i for i in range(10)])
        frame["Label"] = class_id if numeric_labels else name
        frames.append(frame)
    df = pd.concat(frames, ignore_index=True)
    if with_trouble:
        df.loc[3, "f1"] = np.inf
        df.loc[7, "f2"] = np.nan
        df = pd.concat([df, df.iloc[10:15]], ignore_index=True)  # 5 exact duplicate rows
    return df


@pytest.fixture()
def frame():
    return make_frame()


@pytest.fixture()
def csv_path(tmp_path):
    path = tmp_path / "sample.csv"
    make_frame().to_csv(path, index=False)
    return path
