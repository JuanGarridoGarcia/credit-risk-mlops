"""T14.2 and T14.4: the model card (D-095), the parts that need no MLflow."""

from types import SimpleNamespace

import numpy as np
import polars as pl
import pytest

from credit_risk.card import SECTIONS, CardError, check_sections
from credit_risk.explain import importance
from credit_risk.model import PDModel, Prepare


# T14.2
def test_a_card_without_a_section_is_refused_by_name() -> None:
    full = "\n".join(f"## {s}\n\ntext\n" for s in SECTIONS)
    check_sections(full)
    for section in SECTIONS:
        without = full.replace(f"## {section}\n", "")
        with pytest.raises(CardError, match=section):
            check_sections(without)


# T14.4
def test_the_importance_is_the_mean_absolute_contribution_by_hand() -> None:
    train = pl.DataFrame({"int_rate": [10.0, 12.0, 14.0, 20.0], "dti": [5.0, 15.0, 25.0, 35.0]})
    prepare = Prepare("linear", features=("int_rate", "dti")).fit(train)
    estimator = SimpleNamespace(coef_=np.array([[2.0, -1.0]]), intercept_=np.array([0.5]))
    model = PDModel("by hand", prepare, estimator, (36,), platt=(0.5, 0.1))
    rows = pl.DataFrame(
        {"int_rate": [11.0, 19.0, 15.0], "dti": [30.0, 10.0, 20.0], "term": [36, 36, 60]}
    )
    # By hand: Platt's a x coefficient x (value - training mean) / training std; the
    # 60-month loan is not covered and does not count.
    z_rate = (np.array([11.0, 19.0]) - 14.0) / np.std([10.0, 12.0, 14.0, 20.0], ddof=1)
    z_dti = (np.array([30.0, 10.0]) - 20.0) / np.std([5.0, 15.0, 25.0, 35.0], ddof=1)
    expected = {
        "int_rate": float(np.mean(np.abs(0.5 * 2.0 * z_rate))),
        "dti": float(np.mean(np.abs(0.5 * -1.0 * z_dti))),
    }
    found = importance(model, rows)
    assert found == pytest.approx(expected)
    assert list(found) == sorted(expected, key=lambda f: -expected[f])
