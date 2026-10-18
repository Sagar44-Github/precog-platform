import numpy as np
import pytest

from conftest import make_frame
import det_cicids as cicids
from det_lccde import LccdeEnsemble, choose_leaders, lccde_combine


def combine(p, c, leaders):
    return lccde_combine(np.array(p).reshape(3, -1), np.array(c, dtype=float).reshape(3, -1), np.array(leaders))


# ---------- leaders ----------
def test_leader_is_the_model_with_the_best_f1_per_class():
    f1 = [[0.9, 0.5, 0.7], [0.8, 0.6, 0.7], [0.7, 0.4, 0.9]]
    assert choose_leaders(f1).tolist() == [0, 1, 2]


def test_ties_go_to_lightgbm_then_xgboost_then_catboost():
    f1 = [[0.5, 0.2, 0.3], [0.5, 0.9, 0.3], [0.5, 0.9, 0.3]]
    assert choose_leaders(f1).tolist() == [0, 1, 0]


# ---------- the three branches ----------
def test_all_three_agree():
    assert combine([[2], [2], [2]], [[.5], [.5], [.5]], [0, 1, 2]).tolist() == [2]


def test_two_agree_then_the_leader_of_that_class_decides():
    # models 0 and 1 say class 1, model 2 says class 3. Class 1's leader is model 2, so model 2's answer (3) wins.
    assert combine([[1], [1], [3]], [[.5], [.5], [.9]], [0, 2, 0, 0]).tolist() == [3]
    # class 1's leader is model 0, which answered 1.
    assert combine([[1], [1], [3]], [[.5], [.5], [.9]], [0, 0, 0, 0]).tolist() == [1]


def test_first_and_third_agree_counts_as_two_agree_not_all_different():
    # the notebook's chained comparison got this case wrong
    assert combine([[1], [2], [1]], [[.5], [.9], [.5]], [0, 0, 0]).tolist() == [1]


def test_all_different_exactly_one_model_is_its_own_class_leader():
    # answers 1, 2, 3; leaders: class 1 -> model 0 (match), class 2 -> model 0 (no), class 3 -> model 0 (no)
    assert combine([[1], [2], [3]], [[.1], [.9], [.9]], [0, 0, 0, 0]).tolist() == [1]


def test_all_different_none_is_a_leader_most_confident_of_all_three_wins():
    leaders = [0, 1, 2, 0]   # class 1 -> model 1, class 2 -> model 2, class 3 -> model 0: nobody matches
    assert combine([[1], [2], [3]], [[.5], [.9], [.7]], leaders).tolist() == [2]


def test_all_different_several_leaders_only_they_compete():
    leaders = [0, 0, 1, 0]   # model 0 answered 1 (leader 0: yes), model 1 answered 2 (leader 1: yes), model 2 answered 3 (leader 0: no)
    # model 2 is the most confident overall but is not a leader, so model 1 wins
    assert combine([[1], [2], [3]], [[.6], [.8], [.99]], leaders).tolist() == [2]


def test_confidence_ties_go_to_the_lower_model_number():
    leaders = [0, 1, 2, 0]   # none qualifies
    assert combine([[1], [2], [3]], [[.8], [.8], [.8]], leaders).tolist() == [1]


def test_each_row_is_decided_on_its_own_order_does_not_matter():
    rng = np.random.default_rng(1)
    preds = rng.integers(0, 5, size=(3, 300))
    confs = rng.random((3, 300))
    leaders = rng.integers(0, 3, size=5)
    forward = lccde_combine(preds, confs, leaders)
    order = rng.permutation(300)
    shuffled = lccde_combine(preds[:, order], confs[:, order], leaders)
    assert (shuffled == forward[order]).all()


def reference_row(preds, confs, leaders):
    """The same rules written one row at a time, slowly and plainly, to check the fast version against."""
    p = list(preds)
    if p[0] == p[1] == p[2]:
        return p[0]
    if len(set(p)) == 3:
        qualified = [m for m in range(3) if leaders[p[m]] == m]
        if len(qualified) == 1:
            return p[qualified[0]]
        pool = qualified if len(qualified) > 1 else [0, 1, 2]
        best = max(pool, key=lambda m: (confs[m], -m))
        return p[best]
    majority = max(set(p), key=p.count)
    return p[leaders[majority]]


def test_the_fast_version_matches_the_plain_row_by_row_version():
    rng = np.random.default_rng(7)
    preds = rng.integers(0, 6, size=(3, 2000))
    confs = np.round(rng.random((3, 2000)), 1)  # rounding makes ties common on purpose
    leaders = rng.integers(0, 3, size=6)
    fast = lccde_combine(preds, confs, leaders)
    slow = [reference_row(preds[:, i], confs[:, i], leaders) for i in range(2000)]
    assert fast.tolist() == slow


# ---------- the whole ensemble ----------
@pytest.fixture(scope="module")
def trained():
    df = make_frame(seed=3)
    X, y, names = cicids.encode(df)
    X_train, X_test, y_train, y_test = cicids.stratified_split(X, y, seed=0)
    X_fit, X_val, y_fit, y_val = cicids.inner_validation_split(X_train, y_train, seed=0)
    model = LccdeEnsemble(seed=0, threads=1, catboost_iterations=30).fit(X_fit, y_fit, X_val, y_val)
    return model, X_test, y_test


def test_ensemble_learns_the_made_up_data(trained):
    model, X_test, y_test = trained
    outputs = model.predict_all(X_test)
    assert set(outputs) == {"LightGBM", "XGBoost", "CatBoost", "LCCDE"}
    assert (outputs["LCCDE"] == y_test).mean() > 0.9
    assert model.leaders.shape == (7,) and set(model.leaders.tolist()) <= {0, 1, 2}


def test_predict_is_the_lccde_answer(trained):
    model, X_test, _ = trained
    assert (model.predict(X_test) == model.predict_all(X_test)["LCCDE"]).all()


def test_classes_with_gaps_in_their_numbers_still_work():
    df = make_frame(seed=4)
    X, y, _ = cicids.encode(df)
    keep = np.isin(y, [0, 2, 5])  # class ids 0, 2 and 5 only
    model = LccdeEnsemble(seed=0, threads=1, catboost_iterations=20).fit(X[keep], y[keep])
    assert set(np.unique(model.predict(X[keep]))) <= {0, 2, 5}


def test_a_validation_class_the_models_never_saw_is_ignored():
    df = make_frame(seed=5)
    X, y, _ = cicids.encode(df)
    train_mask, val_mask = y != 4, y == 4
    model = LccdeEnsemble(seed=0, threads=1, catboost_iterations=20).fit(X[train_mask], y[train_mask], X[val_mask], y[val_mask])
    assert model.leaders is not None


def test_same_seed_gives_the_same_answers():
    df = make_frame(seed=6)
    X, y, _ = cicids.encode(df)
    a = LccdeEnsemble(seed=1, threads=1, catboost_iterations=20).fit(X, y).predict(X)
    b = LccdeEnsemble(seed=1, threads=1, catboost_iterations=20).fit(X, y).predict(X)
    assert (a == b).all()
