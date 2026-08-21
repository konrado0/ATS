from __future__ import annotations

from decimal import Decimal, ROUND_HALF_EVEN, getcontext


getcontext().prec = 38

ZERO = Decimal("0")
ONE = Decimal("1")
MONEY_QUANTUM = Decimal("0.000001")
QUANTITY_QUANTUM = Decimal("0.000000000001")
PRICE_QUANTUM = Decimal("0.00000001")
WEIGHT_QUANTUM = Decimal("0.000000000001")
RECONCILIATION_TOLERANCE = MONEY_QUANTUM


def decimal_value(value: object) -> Decimal:
    result = value if isinstance(value, Decimal) else Decimal(str(value))
    if not result.is_finite():
        raise ValueError(f"non-finite decimal value: {value!r}")
    return result


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN)


def quantity(value: Decimal) -> Decimal:
    return value.quantize(QUANTITY_QUANTUM, rounding=ROUND_HALF_EVEN)


def price(value: Decimal) -> Decimal:
    return value.quantize(PRICE_QUANTUM, rounding=ROUND_HALF_EVEN)


def weight(value: Decimal) -> Decimal:
    return value.quantize(WEIGHT_QUANTUM, rounding=ROUND_HALF_EVEN)


NUMERIC_POLICY = {
    "implementation": "python_decimal",
    "precision": 38,
    "rounding": "ROUND_HALF_EVEN",
    "money_quantum": str(MONEY_QUANTUM),
    "quantity_quantum": str(QUANTITY_QUANTUM),
    "price_quantum": str(PRICE_QUANTUM),
    "weight_quantum": str(WEIGHT_QUANTUM),
    "float64_boundary": "Decimal(str(value))",
    "reconciliation_tolerance": str(RECONCILIATION_TOLERANCE),
}
