from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from auth import verify_token
from security import get_allowed_employee_domains
from database import User

ROLE_OWNER = "owner"
ROLE_EMPLOYEE = "employee"
ACCOUNT_TYPE_INDIVIDUAL = "individual"
ACCOUNT_TYPE_COMPANY = "company"


def get_org_id(user: User) -> int:
    if user.role == ROLE_EMPLOYEE:
        if not user.owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Personel hesabı yapılandırılmamış",
            )
        return user.owner_id
    return user.id


def require_owner(user: User = Depends(verify_token)) -> User:
    if user.role != ROLE_OWNER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu işlem için şirket sahibi yetkisi gerekir",
        )
    return user


def require_company_account(user: User = Depends(require_owner)) -> User:
    if (user.account_type or ACCOUNT_TYPE_COMPANY) != ACCOUNT_TYPE_COMPANY:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu özellik şirket hesapları içindir",
        )
    return user


def resolve_company_name(user: User, owner: User | None = None) -> str | None:
    if user.role == ROLE_EMPLOYEE:
        return (owner.company_name if owner else None) or None
    if (user.account_type or ACCOUNT_TYPE_COMPANY) != ACCOUNT_TYPE_COMPANY:
        return None
    return user.company_name


def user_response(user: User, owner: User | None = None) -> dict:
    org_owner = owner if user.role == ROLE_EMPLOYEE else user
    company_email_domains: list[str] = []
    if org_owner and (org_owner.account_type or ACCOUNT_TYPE_COMPANY) == ACCOUNT_TYPE_COMPANY:
        company_email_domains = get_allowed_employee_domains(org_owner.email)

    return {
        "username": user.username,
        "email": user.email,
        "role": user.role or ROLE_OWNER,
        "account_type": user.account_type or ACCOUNT_TYPE_COMPANY,
        "owner_id": user.owner_id,
        "company_name": resolve_company_name(user, owner),
        "display_name": (user.display_name or "").strip(),
        "email_verified": bool(user.email_verified),
        "company_email_domains": company_email_domains,
    }


def get_employee_or_404(db: Session, owner_id: int, employee_id: int) -> User:
    employee = (
        db.query(User)
        .filter(
            User.id == employee_id,
            User.role == ROLE_EMPLOYEE,
            User.owner_id == owner_id,
        )
        .first()
    )
    if not employee:
        raise HTTPException(status_code=404, detail="Personel bulunamadı")
    return employee
