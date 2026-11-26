"""Drift of one variable against its reference: PSI, KS, missing and new values (D-139).

The reference fixes the bins once (:func:`fit`), and every month is counted in the same
bins (:func:`measure`):

- a **numeric** variable is cut at the deciles of the reference (repeated cut points are
  kept once, so a variable that is almost always 0 makes few bins, never empty twins);
  a value below the first cut or above the last falls in the bin at that end;
- a **categorical** variable has one bin per category seen in the reference and one more
  for any category never seen ("new");
- both have one bin for missing values.

PSI = sum over bins of ``(month - reference) * ln(month / reference)``, with every share
floored at 0.01% so that an empty bin never gives an infinite value. The KS statistic is
kept for information only, numeric variables only, against a sample of the reference.
"""

from dataclasses import dataclass
from typing import Final, Literal

import numpy as np
import numpy.typing as npt
import polars as pl
from scipy.stats import ks_2samp

Kind = Literal["numeric", "categorical", "prediction"]
Array = npt.NDArray[np.float64]

#: The cut points of a numeric variable: its deciles in the reference.
QUANTILES: Final = tuple(round(q / 10, 1) for q in range(1, 10))
#: The smallest share a bin can count with in the PSI (0.01%).
FLOOR: Final = 1e-4
#: Values of the reference kept for the KS statistic, drawn with a fixed seed.
SAMPLE: Final = 5_000
SEED: Final = 0


@dataclass(frozen=True)
class Bins:
    """The bins of one variable in a reference, and the share of the reference in each.

    ``shares`` has, in order: one share per bin of values (``len(edges) + 1`` numeric
    bins, or one per category), then for a categorical variable the "new" bin, and last
    the missing-value bin.
    """

    subject: str
    kind: Kind
    rows: int
    nulls: int
    shares: tuple[float, ...]
    edges: tuple[float, ...] = ()
    categories: tuple[str, ...] = ()
    minimum: float | None = None
    maximum: float | None = None
    sample: tuple[float, ...] = ()

    @property
    def numeric(self) -> bool:
        return self.kind != "categorical"


@dataclass(frozen=True)
class Drift:
    """One variable in one month, against its reference."""

    subject: str
    kind: Kind
    rows: int
    psi: float
    ks: float | None
    null_share: float
    #: Categories never seen in the reference, or numbers outside its range.
    new_values: int


def _numbers(values: pl.Series) -> Array:
    return np.asarray(values.cast(pl.Float64).drop_nulls().drop_nans().to_numpy(), np.float64)


def _missing(values: pl.Series) -> int:
    if values.dtype.is_float():
        return int(values.is_null().sum()) + int(values.is_nan().fill_null(False).sum())
    return int(values.is_null().sum())


def _numeric_counts(edges: tuple[float, ...], numbers: Array) -> npt.NDArray[np.int64]:
    # side="left": a value equal to a cut point belongs to the bin that ends there.
    index = np.searchsorted(np.asarray(edges, np.float64), numbers, side="left")
    return np.bincount(index, minlength=len(edges) + 1).astype(np.int64)


def _categorical_counts(
    categories: tuple[str, ...], values: pl.Series
) -> tuple[npt.NDArray[np.int64], int]:
    texts = values.drop_nulls().cast(pl.String)
    counted = dict(texts.value_counts().iter_rows())
    known = np.array([counted.get(c, 0) for c in categories], dtype=np.int64)
    new = int(texts.len() - known.sum())
    return known, new


def counts(bins: Bins, values: pl.Series) -> npt.NDArray[np.int64]:
    """How many of ``values`` fall in each bin of ``bins``, in the order of its shares."""
    missing = _missing(values)
    if bins.numeric:
        found = _numeric_counts(bins.edges, _numbers(values))
        return np.append(found, missing)
    known, new = _categorical_counts(bins.categories, values)
    return np.append(known, [new, missing])


def _shares(found: npt.NDArray[np.int64]) -> tuple[float, ...]:
    total = int(found.sum())
    return tuple(float(c) / total if total else 0.0 for c in found)


def fit(subject: str, kind: Kind, values: pl.Series) -> Bins:
    """The bins of ``values``, the reference of one variable."""
    rows, nulls = values.len(), _missing(values)
    if kind == "categorical":
        categories = tuple(sorted(values.drop_nulls().cast(pl.String).unique().to_list()))
        bins = Bins(subject, kind, rows, nulls, (), categories=categories)
        return Bins(
            subject, kind, rows, nulls, _shares(counts(bins, values)), categories=categories
        )
    numbers = _numbers(values)
    edges: tuple[float, ...] = ()
    minimum = maximum = None
    sample: tuple[float, ...] = ()
    if numbers.size:
        edges = tuple(float(e) for e in np.unique(np.quantile(numbers, QUANTILES)))
        minimum, maximum = float(numbers.min()), float(numbers.max())
        drawn = numbers
        if numbers.size > SAMPLE:
            drawn = np.random.default_rng(SEED).choice(numbers, SAMPLE, replace=False)
        sample = tuple(float(v) for v in drawn)
    bins = Bins(subject, kind, rows, nulls, (), edges=edges)
    return Bins(
        subject,
        kind,
        rows,
        nulls,
        _shares(counts(bins, values)),
        edges=edges,
        minimum=minimum,
        maximum=maximum,
        sample=sample,
    )


def psi(reference: tuple[float, ...] | Array, month: tuple[float, ...] | Array) -> float:
    """Population stability index of two sets of shares over the same bins."""
    expected = np.maximum(np.asarray(reference, np.float64), FLOOR)
    actual = np.maximum(np.asarray(month, np.float64), FLOOR)
    if expected.shape != actual.shape:
        raise ValueError(f"different bins: {expected.size} and {actual.size}")
    return float(np.sum((actual - expected) * np.log(actual / expected)))


def ks(sample: tuple[float, ...], values: pl.Series) -> float | None:
    """Two-sample Kolmogorov-Smirnov statistic of the month against the reference sample."""
    numbers = _numbers(values)
    if not sample or numbers.size == 0:
        return None
    return float(ks_2samp(np.asarray(sample, np.float64), numbers).statistic)


def _new_values(bins: Bins, values: pl.Series) -> int:
    if not bins.numeric:
        return int(counts(bins, values)[-2])
    numbers = _numbers(values)
    if bins.minimum is None or bins.maximum is None:
        return int(numbers.size)
    return int(((numbers < bins.minimum) | (numbers > bins.maximum)).sum())


def measure(bins: Bins, values: pl.Series) -> Drift:
    """The drift of one month of ``values`` against ``bins``."""
    if values.len() == 0:
        raise ValueError(f"no values of {bins.subject} to measure")
    found = counts(bins, values)
    return Drift(
        subject=bins.subject,
        kind=bins.kind,
        rows=values.len(),
        psi=psi(bins.shares, _shares(found)),
        ks=ks(bins.sample, values) if bins.numeric else None,
        null_share=float(found[-1]) / values.len(),
        new_values=_new_values(bins, values),
    )
