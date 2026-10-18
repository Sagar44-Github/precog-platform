"""Detection numbers. 'Attack' means any class that is not BENIGN."""
import numpy as np
from sklearn.metrics import f1_score


def _ratio(numerator, denominator):
    return float(numerator) / float(denominator) if denominator else None


def binary_metrics(y_true, y_pred, benign_id):
    """Treat every non-benign class as 'attack' and report precision, recall, F1 and the false-positive rate.
    A ratio that cannot be calculated (for example no attacks in the data) is None, never a made-up 0."""
    truth = np.asarray(y_true) != benign_id
    guess = np.asarray(y_pred) != benign_id
    tp = int((truth & guess).sum())
    fp = int((~truth & guess).sum())
    tn = int((~truth & ~guess).sum())
    fn = int((truth & ~guess).sum())
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = None if precision is None or recall is None or (precision + recall) == 0 else 2 * precision * recall / (precision + recall)
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": precision, "recall": recall, "f1": f1,
        "false_positive_rate": _ratio(fp, fp + tn),
    }


def macro_f1(y_true, y_pred):
    return float(f1_score(y_true, y_pred, average="macro", zero_division=0))


def per_class_f1(y_true, y_pred, class_names):
    scores = f1_score(y_true, y_pred, labels=list(range(len(class_names))), average=None, zero_division=0)
    return {name: float(score) for name, score in zip(class_names, scores)}


def unseen_detection_rate(y_pred, hidden_mask, benign_id):
    """Of the rows of the attack type the model never saw, the share it still flagged as some kind of attack."""
    hidden_mask = np.asarray(hidden_mask, dtype=bool)
    return _ratio((np.asarray(y_pred)[hidden_mask] != benign_id).sum(), hidden_mask.sum())
