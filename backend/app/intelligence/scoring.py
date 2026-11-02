"""Mathematical scoring formulas for category deficiency scores and SDI calculations."""

from collections.abc import Sequence
from decimal import ROUND_HALF_UP, Decimal

from app.intelligence.constants import (
    MAX_PHYSICAL_SEVERITY,
    WEIGHT_SUM_TOLERANCE,
)

TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


def calculate_category_deficiency_score(severities: Sequence[int]) -> Decimal:
    """Calculate normalized category deficiency score (0-100) from verified physical severities.

    Formula:
        mean_severity = (sum of severities) / (number of observations)
        category_score = (mean_severity / MAX_PHYSICAL_SEVERITY) * 100.0

    Args:
        severities: Non-empty sequence of verified severities (each between 1 and 5).

    Returns:
        Decimal: Normalized category score rounded to two decimal places [20.00, 100.00].

    Raises:
        ValueError: If severities sequence is empty or contains out-of-bounds values.
    """
    if not severities:
        raise ValueError("Cannot calculate category deficiency score from empty observations.")

    for s in severities:
        if s < 1 or s > 5:
            raise ValueError(f"Severity score must be an integer between 1 and 5, got {s}.")

    total_severity = Decimal(sum(severities))
    count = Decimal(len(severities))
    mean_severity = total_severity / count

    raw_score = (mean_severity / MAX_PHYSICAL_SEVERITY) * Decimal("100.0")
    score_quantized = raw_score.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)

    # Bound defensively between 0.00 and 100.00
    bounded = max(Decimal("0.00"), min(Decimal("100.00"), score_quantized))
    return bounded


def validate_configuration_weights(weights: Sequence[Decimal]) -> None:
    """Validate that category weights are non-negative and sum to 1.0 within tolerance.

    Args:
        weights: Sequence of assigned category weights.

    Raises:
        ValueError: If any weight is negative or the sum deviates from 1.0000.
    """
    if not weights:
        raise ValueError("Scoring configuration must have at least one category weight.")

    total_weight = Decimal("0.0000")
    for w in weights:
        if w < Decimal("0.0000"):
            raise ValueError(f"Category weight must be non-negative, got {w}.")
        total_weight += w

    discrepancy = abs(total_weight - Decimal("1.0000"))
    if discrepancy > WEIGHT_SUM_TOLERANCE:
        raise ValueError(
            f"Configured category weights must sum to 1.0 within tolerance {WEIGHT_SUM_TOLERANCE}; "
            f"actual sum is {total_weight} (deviation: {discrepancy})."
        )


def calculate_sdi(
    category_scores: dict[int, Decimal | None],
    assigned_weights: dict[int, Decimal],
) -> tuple[Decimal | None, dict[int, Decimal], dict[int, Decimal], Decimal]:
    """Calculate weighted Safety Deficiency Index (SDI) with available-weight normalization.

    Formula:
        W_avail = sum(w_i for i in observed_categories)
        w_i' = w_i / W_avail  (re-normalized weight)
        contribution_i = category_score_i * w_i'
        SDI = sum(contribution_i) = sum(category_score_i * w_i) / W_avail
        completeness = (count of observed categories / total categories) * 100.0

    If no category has sufficient observations (W_avail == 0):
        SDI is None (unavailable), completeness is 0.00%.

    Args:
        category_scores: Mapping of category_id -> Decimal score (or None if unobserved).
        assigned_weights: Mapping of category_id -> assigned Decimal weight.

    Returns:
        tuple containing:
            - sdi (Decimal | None): Final composite SDI (0.00 to 100.00) or None.
            - normalized_weights (dict[int, Decimal]): Re-normalized category weights.
            - contributions (dict[int, Decimal]): Weighted category score contributions.
            - completeness_pct (Decimal): Completeness percentage (0.00 to 100.00).
    """
    total_categories = len(assigned_weights)
    if total_categories == 0:
        raise ValueError("Cannot calculate SDI without configured category weights.")

    observed_ids = [
        cid
        for cid, score in category_scores.items()
        if score is not None and cid in assigned_weights
    ]

    normalized_weights: dict[int, Decimal | None] = dict.fromkeys(assigned_weights)
    contributions: dict[int, Decimal | None] = dict.fromkeys(assigned_weights)

    # Zero coverage case: no categories observed
    if not observed_ids:
        return None, normalized_weights, contributions, Decimal("0.00")

    available_weight_sum = sum(assigned_weights[cid] for cid in observed_ids)
    if available_weight_sum == Decimal("0.0000"):
        return None, normalized_weights, contributions, Decimal("0.00")

    completeness_pct = (available_weight_sum * Decimal("100.0")).quantize(
        TWO_PLACES, rounding=ROUND_HALF_UP
    )

    weighted_sum = Decimal("0.0000")

    for cid in observed_ids:
        score = category_scores[cid]
        assert score is not None
        assigned_w = assigned_weights[cid]

        # Re-normalized weight
        norm_w = (assigned_w / available_weight_sum).quantize(FOUR_PLACES, rounding=ROUND_HALF_UP)
        normalized_weights[cid] = norm_w

        # Individual contribution
        contrib = (score * (assigned_w / available_weight_sum)).quantize(
            TWO_PLACES, rounding=ROUND_HALF_UP
        )
        contributions[cid] = contrib

        weighted_sum += score * assigned_w

    raw_sdi = weighted_sum / available_weight_sum
    sdi_quantized = raw_sdi.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
    final_sdi = max(Decimal("0.00"), min(Decimal("100.00"), sdi_quantized))

    return final_sdi, normalized_weights, contributions, completeness_pct
