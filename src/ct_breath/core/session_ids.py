import re


SESSION_HEADER = "X-RespiraScope-Session"
SESSION_QUERY_PARAM = "session_id"
SESSION_ROOM_PREFIX = "session:"
SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def normalize_session_id(value: object | None) -> str | None:
    if value is None:
        return None
    session_id = str(value).strip()
    if not session_id:
        return None
    if not SESSION_ID_PATTERN.fullmatch(session_id):
        raise ValueError("Invalid RespiraScope session id")
    return session_id


def session_room(session_id: str) -> str:
    return f"{SESSION_ROOM_PREFIX}{session_id}"
