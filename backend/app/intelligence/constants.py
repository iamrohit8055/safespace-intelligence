"""Methodology constants and defaults for the SafeSpace Intelligence Engine."""

from decimal import Decimal

# Default active scoring configuration version and name
DEFAULT_CONFIGURATION_VERSION = "v1.0.0"
BASELINE_METHODOLOGY_NAME = "Baseline Infrastructure Deficiency Methodology"

# Baseline category weights matching migration 0004
BASELINE_WEIGHTS: dict[str, Decimal] = {
    "STREET_LIGHTING": Decimal("0.3000"),
    "PEDESTRIAN_PATHWAYS": Decimal("0.2500"),
    "VISIBILITY": Decimal("0.1500"),
    "PUBLIC_ASSISTANCE": Decimal("0.2000"),
    "MAINTENANCE": Decimal("0.1000"),
}

# Numerical tolerance for validating that category weights sum to 1.0000
WEIGHT_SUM_TOLERANCE = Decimal("0.0001")

# Severity scale bounds (physical deficiency rating)
SEVERITY_MIN = 1
SEVERITY_MAX = 5
MAX_PHYSICAL_SEVERITY = Decimal("5.0")

# Scale bounds for Safety Deficiency Index
SDI_MIN_SCORE = Decimal("0.00")
SDI_MAX_SCORE = Decimal("100.00")

# Minimum observations required in a category for it to be considered OBSERVED
DEFAULT_MIN_OBSERVATIONS = 1

# Category availability states
STATE_OBSERVED = "OBSERVED"
STATE_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
