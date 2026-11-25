"""What the API decides about a purchase the investor reports (D-124 to D-129).

The investor sends, for each purchase, its own order number, the ``prediction_id`` of the
answer it decided on and the amount. :func:`judge` decides one order against what is
stored: the same order again is the stored purchase (``stored_earlier``); the same order
number with another content is a conflict (409); an unknown prediction, an amount that is
not a whole number of 25 dollar notes, or a client's share above the loan's amount is
refused (422). Anything else is a new purchase, with where it stands against the buy rule
of its answer: exceptions are recorded, never refused (D-126).

The store reads what :func:`judge` needs and writes what it decides, in the request's
transaction (D-121); the tests' store in memory does the same with dictionaries.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field

#: Notes of Lending Club: every amount is a whole number of them (D-128).
NOTE: Final = 25

Status = Literal["created", "stored_earlier", "refused"]
Policy = Literal["passes", "below_minimum", "no_threshold", "not_covered"]


class Order(BaseModel):
    """One purchase as the investor reports it."""

    model_config = ConfigDict(extra="forbid", strict=True)

    order_id: str = Field(min_length=1, max_length=100)
    prediction_id: int
    amount: int


@dataclass(frozen=True)
class Prediction:
    """What a purchase needs to know of the answer it was decided on."""

    prediction_id: int
    loan_id: int
    ead: float | None
    covered: bool
    minimum: float | None
    passes: bool | None


@dataclass(frozen=True)
class Stored:
    """A purchase already in the table."""

    purchase_id: int
    client: str
    order_id: str
    prediction_id: int
    loan_id: int
    amount: Decimal
    policy: Policy
    at: Any = None


@dataclass(frozen=True)
class Outcome:
    """What happens to one order: a purchase (new or stored) or a refusal."""

    status: Status
    code: int = 200
    errors: tuple[dict[str, Any], ...] = ()
    #: For a new purchase, the row to insert; for a repeat, the stored one.
    loan_id: int | None = None
    policy: Policy | None = None
    stored: Stored | None = None


def policy_of(prediction: Prediction) -> Policy:
    """Where a purchase stands against the buy rule of its answer (D-112, D-126)."""
    if not prediction.covered:
        return "not_covered"
    if prediction.minimum is None:
        return "no_threshold"
    return "passes" if prediction.passes else "below_minimum"


def _refused(code: int, field: str, message: str) -> Outcome:
    return Outcome("refused", code, ({"column": field, "message": message},))


def judge(
    order: Order,
    existing: Stored | None,
    prediction: Prediction | None,
    held: Decimal,
) -> Outcome:
    """Decide one order: ``existing`` is the client's purchase with this order number,
    ``held`` what the client already holds of the prediction's loan."""
    if existing is not None:
        same = existing.prediction_id == order.prediction_id
        if same and existing.amount == Decimal(order.amount):
            return Outcome("stored_earlier", stored=existing)
        return _refused(409, "order_id", "this order number was already used for another purchase")
    if prediction is None:
        return _refused(422, "prediction_id", "no prediction has this id")
    if order.amount <= 0 or order.amount % NOTE:
        return _refused(422, "amount", f"the amount must be a positive multiple of {NOTE}")
    if prediction.ead is not None and held + order.amount > Decimal(str(prediction.ead)):
        return _refused(
            422,
            "amount",
            f"the client would hold {held + order.amount} of a loan of {prediction.ead}",
        )
    return Outcome("created", loan_id=prediction.loan_id, policy=policy_of(prediction))
