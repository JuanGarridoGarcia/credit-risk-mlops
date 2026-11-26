"""T28.1: the share of first-year defaults on the real data (D-143), approved by Juan on
2026-11-26.

Needs the real deliveries loaded up to T0, shared with the snapshot tests
(``tests/data/conftest.py``).
"""

from typing import Any

import pytest

from credit_risk.monitoring import store
from credit_risk.snapshot import Manifest
from tests.data.conftest import T0

pytestmark = pytest.mark.data

#: data_audit.md 4.2: 41% of the bad 36-month loans missed their first payment within 12
#: months of issue.
AUDIT_SHARE_36 = 0.41


# T28.1
def test_the_first_year_share_at_t0_agrees_with_the_audit(t0_conn: Any, first: Manifest) -> None:
    assert first.cutoff == T0
    shares = store.first_year_shares(t0_conn, T0)
    print(f"\nshare of first-year defaults at {T0}: by term {shares.by_term}")
    for (term, grade), share in sorted(shares.by_grade.items()):
        print(f"  {term} months, grade {grade}: {share:.3f}")
    assert set(shares.by_term) == {36}, "at T0 only 36-month loans have matured"
    assert shares.by_term[36] == pytest.approx(AUDIT_SHARE_36, abs=0.05)
