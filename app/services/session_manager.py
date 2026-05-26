from app.models.call_session import CallSession
from typing import Optional

sessions = {}

def create_session(call_id: str, mobile_number: str) -> CallSession:
    session = CallSession(call_id=call_id, mobile_number=mobile_number)
    sessions[call_id] = session
    return session

def get_session(call_id: str) -> Optional[CallSession]:
    return sessions.get(call_id)

def update_session(session: CallSession) -> None:
    sessions[session.call_id] = session

def delete_session(call_id: str) -> None:
    sessions.pop(call_id, None)