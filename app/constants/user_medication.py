from enum import Enum

class TrackingPurpose(str, Enum):
    ACTIVE_USE = "active_use"
    INACTIVE_HISTORY = "inactive_history"
    EDUCATION = "education"
    CONSIDERING = "considering"
    OTHER = "other"

TRACKING_PURPOSE_LABELS = {
    "active_use": "Currently taking",
    "inactive_history": "Previously took",
    "education": "Learning / research",
    "considering": "Considering taking",
    "other": "Other",
}