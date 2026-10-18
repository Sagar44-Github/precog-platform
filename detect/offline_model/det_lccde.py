"""LCCDE: Leader Class and Confidence Decision Ensemble.

The idea comes from the Western OC2 Lab notebook LCCDE_IDS_GlobeCom22.ipynb (MIT licence):
train LightGBM, XGBoost and CatBoost; for every class find the model that is best at that class (its
"leader"); then combine the three models' answers:
  * all three agree                -> use that class;
  * all three disagree             -> keep the answers whose own model is the leader for the answered class;
                                      if exactly one is left use it, otherwise take the most confident one
                                      (among the leaders if several, among all three if none);
  * two agree and one disagrees    -> take the majority class, then use the answer of that class's leader model.

Differences from the notebook, on purpose (the notebook is a demonstration):
  1. Leaders are chosen on a validation part of the TRAINING data, not on the test data (no peeking at the test set).
  2. It works on all rows at once instead of row by row (minutes become seconds).
  3. The notebook's 'all three disagree' branch keeps its lists between rows and compares with a chained
     '!=' that also catches the 'first and third agree' case; here each row is decided on its own and
     'all different' really means all three different.
"""
import numpy as np
from sklearn.metrics import f1_score

MODEL_NAMES = ("LightGBM", "XGBoost", "CatBoost")


def make_base_models(seed=0, threads=0, catboost_iterations=1000):
    """The three base learners with the library defaults the notebook uses. threads=0 means 'all cores'."""
    import lightgbm as lgb
    import xgboost as xgb
    import catboost as cbt

    n_jobs = -1 if threads in (0, None) else int(threads)
    return [
        lgb.LGBMClassifier(random_state=seed, n_jobs=n_jobs, verbose=-1),
        xgb.XGBClassifier(random_state=seed, n_jobs=n_jobs),
        cbt.CatBoostClassifier(verbose=0, boosting_type="Plain", random_seed=seed, thread_count=n_jobs, allow_writing_files=False,
                               iterations=int(catboost_iterations)),
    ]


def choose_leaders(f1_per_model):
    """f1_per_model: array shape (3, number_of_classes). Returns, for each class, the index (0, 1, 2) of the best
    model. A tie goes to LightGBM, then XGBoost, then CatBoost, like the notebook."""
    f1_per_model = np.asarray(f1_per_model, dtype=float)
    best = f1_per_model.max(axis=0)
    leaders = np.where(f1_per_model[0] == best, 0, np.where(f1_per_model[1] == best, 1, 2))
    return leaders.astype(int)


def lccde_combine(preds, confs, leaders):
    """preds, confs: arrays of shape (3, n) with each model's class index and confidence for each row.
    leaders: shape (number_of_classes,). Returns the final class index for every row."""
    preds = np.asarray(preds, dtype=int)
    confs = np.asarray(confs, dtype=float)
    leaders = np.asarray(leaders, dtype=int)
    p1, p2, p3 = preds
    n = p1.shape[0]
    final = np.empty(n, dtype=int)

    all_same = (p1 == p2) & (p2 == p3)
    final[all_same] = p1[all_same]

    all_different = (p1 != p2) & (p2 != p3) & (p1 != p3)
    idx = np.where(all_different)[0]
    if idx.size:
        own_answer_is_leader = np.stack([leaders[preds[m, idx]] == m for m in range(3)])
        how_many = own_answer_is_leader.sum(axis=0)
        leader_confs = np.where(own_answer_is_leader, confs[:, idx], -np.inf)
        pool = np.where(how_many[None, :] > 1, leader_confs, confs[:, idx])  # several leaders: only them; none: all three
        chosen = np.argmax(pool, axis=0)                                    # ties go to the lower model number
        chosen = np.where(how_many == 1, np.argmax(own_answer_is_leader, axis=0), chosen)
        final[idx] = preds[chosen, idx]

    two_agree = ~all_same & ~all_different
    majority = np.where(p1 == p2, p1, np.where(p1 == p3, p1, p2))
    rows = np.where(two_agree)[0]
    if rows.size:
        leader_model = leaders[majority[rows]]
        final[rows] = preds[leader_model, rows]
    return final


class LccdeEnsemble:
    def __init__(self, seed=0, threads=0, catboost_iterations=1000):
        self.seed, self.threads, self.catboost_iterations = seed, threads, catboost_iterations
        self.models = []
        self.classes_ = None
        self.leaders = None
        self.validation_f1 = None

    def fit(self, X_train, y_train, X_val=None, y_val=None):
        X_train = np.asarray(X_train, dtype=np.float32)
        y_train = np.asarray(y_train, dtype=int)
        self.classes_ = np.unique(y_train)
        y_index = np.searchsorted(self.classes_, y_train)  # models need classes numbered 0..k-1 without gaps
        self.models = make_base_models(self.seed, self.threads, self.catboost_iterations)
        for model in self.models:
            model.fit(X_train, y_index)

        k = len(self.classes_)
        X_val_arr = y_val_index = None
        if X_val is not None and len(y_val) > 0:
            y_val = np.asarray(y_val, dtype=int)
            known = np.isin(y_val, self.classes_)  # rows of a class the models never saw cannot help choose leaders
            if known.any():
                X_val_arr = np.asarray(X_val, dtype=np.float32)[known]
                y_val_index = np.searchsorted(self.classes_, y_val[known])
        if X_val_arr is None:  # no usable validation rows: fall back to the training rows (less honest, but never fails)
            X_val_arr, y_val_index = X_train, y_index
        per_model = []
        for model in self.models:
            predicted = np.asarray(model.predict(X_val_arr)).ravel().astype(int)
            per_model.append(f1_score(y_val_index, predicted, labels=list(range(k)), average=None, zero_division=0))
        self.validation_f1 = np.vstack(per_model)
        self.leaders = choose_leaders(self.validation_f1)
        return self

    def _base_outputs(self, X):
        X = np.asarray(X, dtype=np.float32)
        preds, confs = [], []
        for model in self.models:
            probabilities = np.asarray(model.predict_proba(X))
            preds.append(probabilities.argmax(axis=1))
            confs.append(probabilities.max(axis=1))
        return np.vstack(preds), np.vstack(confs)

    def predict_all(self, X):
        """Returns {'LightGBM': ids, 'XGBoost': ids, 'CatBoost': ids, 'LCCDE': ids} using the original class ids."""
        preds, confs = self._base_outputs(X)
        combined = lccde_combine(preds, confs, self.leaders)
        result = {name: self.classes_[preds[i]] for i, name in enumerate(MODEL_NAMES)}
        result["LCCDE"] = self.classes_[combined]
        return result

    def predict(self, X):
        return self.predict_all(X)["LCCDE"]
