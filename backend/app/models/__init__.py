"""SQLAlchemy declarative models for SafeSpace Intelligence."""

from app.models.confidence import (
    AreaConfidenceComponent,
    AreaConfidenceScore,
    ConfidenceConfiguration,
    ConfidenceConfigurationFactor,
    ReportConfidenceComponent,
    ReportConfidenceScore,
)
from app.models.duplicates import (
    DuplicateCandidate,
    DuplicateDetectionConfiguration,
    DuplicateReviewHistory,
)
from app.models.geography import AdministrativeArea
from app.models.iam import Role, User, UserRole
from app.models.intelligence import (
    AreaScore,
    ScoreComponent,
    ScoringConfiguration,
    ScoringConfigurationWeight,
)
from app.models.maintenance import MaintenanceTask, MaintenanceTaskEvent
from app.models.notifications import Notification
from app.models.priority import AreaPriorityScore, PriorityConfiguration
from app.models.reporting import Report, ReportCategory, ReportMedia
from app.models.verification import ReportStatusHistory, ReportVerification

__all__ = [
    "AdministrativeArea",
    "AreaConfidenceComponent",
    "AreaConfidenceScore",
    "AreaPriorityScore",
    "AreaScore",
    "ConfidenceConfiguration",
    "ConfidenceConfigurationFactor",
    "DuplicateCandidate",
    "DuplicateDetectionConfiguration",
    "DuplicateReviewHistory",
    "MaintenanceTask",
    "MaintenanceTaskEvent",
    "Notification",
    "PriorityConfiguration",
    "Report",
    "ReportCategory",
    "ReportConfidenceComponent",
    "ReportConfidenceScore",
    "ReportMedia",
    "ReportStatusHistory",
    "ReportVerification",
    "Role",
    "ScoreComponent",
    "ScoringConfiguration",
    "ScoringConfigurationWeight",
    "User",
    "UserRole",
]
