from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import settings
from database import User, get_db
from security import verify_password

security = HTTPBearer()


def create_access_token(
    user_id: int,
    username: str,
    remember_me: bool = False,
    token_version: int = 0,
) -> tuple[str, int]:
    if remember_me:
        expire_delta = timedelta(days=settings.remember_me_expire_days)
    else:
        expire_delta = timedelta(minutes=settings.access_token_expire_minutes)

    expire = datetime.utcnow() + expire_delta
    payload = {
        "exp": expire,
        "sub": str(user_id),
        "username": username,
        "remember": remember_me,
        "tv": token_version,
    }
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token, int(expire_delta.total_seconds())


def bump_token_version(user: User) -> None:
    user.token_version = (user.token_version or 0) + 1


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.query(User).filter(User.username == username.lower()).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def require_verified_user(user: User) -> User:
    if not settings.email_verification_enabled:
        return user
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="E-posta adresiniz doğrulanmamış. Gelen kutunuzu kontrol edin.",
        )
    return user


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.secret_key,
            algorithms=[settings.algorithm],
        )
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token")

        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı bulunamadı")

        token_version = payload.get("tv", 0)
        if token_version != (user.token_version or 0):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Oturum süresi doldu. Lütfen tekrar giriş yapın.",
            )

        if settings.email_verification_enabled and not user.email_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="E-posta adresiniz doğrulanmamış. Gelen kutunuzu kontrol edin.",
            )

        return user
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum süresi doldu")
