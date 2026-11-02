"""Intelligence Engine module for SafeSpace Intelligence."""

from app.intelligence.aggregation import (
    get_eligible_verified_reports,
    group_observations_by_category,
)
from app.intelligence.constants import (
    BASELINE_METHODOLOGY_NAME,
    BASELINE_WEIGHTS,
    DEFAULT_CONFIGURATION_VERSION,
    DEFAULT_MIN_OBSERVATIONS,
    SDI_MAX_SCORE,
    SDI_MIN_SCORE,
    SEVERITY_MAX,
    SEVERITY_MIN,
    STATE_INSUFFICIENT_DATA,
    STATE_OBSERVED,
    WEIGHT_SUM_TOLERANCE,
)
from app.intelligence.scoring import (
    calculate_category_deficiency_score,
    calculate_sdi,
    validate_configuration_weights,
)
from app.intelligence.service import (
    calculate_area_sdi,
    get_active_scoring_configuration,
    get_area_score_by_id,
    get_area_sdi_history,
    get_current_area_sdi,
    list_scoring_configurations,
)

__all__ = [
    "BASELINE_METHODOLOGY_NAME",
    "BASELINE_WEIGHTS",
    "DEFAULT_CONFIGURATION_VERSION",
    "DEFAULT_MIN_OBSERVATIONS",
    "SDI_MAX_SCORE",
    "SDI_MIN_SCORE",
    "SEVERITY_MAX",
    "SEVERITY_MIN",
    "STATE_INSUFFICIENT_DATA",
    "STATE_OBSERVED",
    "WEIGHT_SUM_TOLERANCE",
    "calculate_area_sdi",
    "calculate_category_deficiency_score",
    "calculate_sdi",
    "get_active_scoring_configuration",
    "get_area_score_by_id",
    "get_area_sdi_history",
    "get_current_area_sdi",
    "get_eligible_verified_reports",
    "group_observations_by_category",
    "list_scoring_configurations",
    "validate_configuration_weights",
]
