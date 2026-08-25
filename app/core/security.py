import hashlib

from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def hash_token(token: str) -> str:
    """Fast, deterministic hash for opaque high-entropy tokens (e.g. refresh tokens) - unlike
    bcrypt above, which is deliberately slow and meant for low-entropy user passwords, this
    needs to run on every request without a noticeable cost."""
    return hashlib.sha256(token.encode()).hexdigest()


# TODO(phase-2): JWT creation/validation logic — separate module, not this one.
