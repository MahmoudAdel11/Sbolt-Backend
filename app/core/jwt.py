from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.core.config import get_settings
from app.core.exceptions import UnauthorizedError


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except JWTError as exc:
        raise UnauthorizedError("Invalid or expired token.") from exc


# TODO(phase-2): "get_current_user" dependency built on decode_access_token — added with endpoints.
