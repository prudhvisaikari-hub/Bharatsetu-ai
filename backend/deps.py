from typing import Optional
from fastapi import Depends, HTTPException, status
from . import config
from .auth import get_current_user_optional
from .db.models import User

def resolve_msme_id(
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> str:
    """Resolves the tenant msme_id for the current request.
    If a user is logged in, returns user.msme_id.
    If not logged in: returns 'demo' only when DEMO_MODE is True, else raises 401.
    """
    if current_user:
        return current_user.msme_id
    if config.DEMO_MODE:
        return "demo"
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )

def require_official_role(
    current_user: Optional[User] = Depends(get_current_user_optional)
) -> Optional[User]:
    """Requires an authenticated user with 'official' or 'admin' role.
    In DEMO_MODE, anonymous requests are permitted for read-only aggregate views.
    """
    if current_user:
        if current_user.role not in ("official", "admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Official or administrator role required"
            )
        return current_user
    if config.DEMO_MODE:
        return None
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
