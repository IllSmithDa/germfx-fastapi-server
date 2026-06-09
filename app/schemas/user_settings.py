from pydantic import BaseModel, ConfigDict
from typing import Optional

class UserSettingsResponse(BaseModel):
    id: int
    user_id: int
    theme: str
    default_report_range: str
    top_symptom_limit: int
    remember_last_medication: bool
    recent_suggestions_first: bool
    default_recall_state: str
    default_recall_type: str
    model_config = ConfigDict(from_attributes=True)


class UserSettingsUpdateRequest(BaseModel):
    theme: Optional[str] = None
    default_report_range: Optional[str] = None
    top_symptom_limit: Optional[int] = None
    remember_last_medication: Optional[bool] = None
    recent_suggestions_first: Optional[bool] = None
    default_recall_state: Optional[str] = None
    default_recall_type: Optional[str] = None