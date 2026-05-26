from enum import Enum
from pydantic import BaseModel
from typing import Optional


class Language(str, Enum):
    HINDI   = "hi-IN"
    MARATHI = "mr-IN"


class CallStep(str, Enum):
    WELCOME         = "WELCOME"
    LANGUAGE_SELECT = "LANGUAGE_SELECT"
    NAME_CAPTURE    = "NAME_CAPTURE"
    AUTH            = "AUTH"
    USE_CASE_SELECT = "USE_CASE_SELECT"
    DATA_CAPTURE    = "DATA_CAPTURE"
    TICKET_CREATE   = "TICKET_CREATE"
    ESCALATE        = "ESCALATE"
    END             = "END"


class GrievanceData(BaseModel):
    crop_name:   Optional[str] = None
    crop_stage:  Optional[str] = None
    loss_date:   Optional[str] = None
    loss_reason: Optional[str] = None


class CallSession(BaseModel):
    call_id:               str
    mobile_number:         Optional[str] = None
    step:                  CallStep      = CallStep.WELCOME
    language:              Optional[Language] = None
    auth_passed:           bool          = False
    auth_retries:          int           = 0
    language_retries:      int           = 0
    name_retries:          int           = 0
    farmer_record:         Optional[dict] = None
    grievance:             GrievanceData = GrievanceData()
    auth_substep:          Optional[str] = None