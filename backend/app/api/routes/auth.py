from fastapi import APIRouter, Depends, HTTPException, Header, Request
import os
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models import Merchant, User
from app.core.config import settings
from app.security import ROLES, create_access_token, get_current_user, hash_password, verify_password
from app.audit import record_event
from app.audit.actions import AUTH_LOGIN_SUCCESS, AUTH_LOGIN_FAILURE, AUTH_REGISTER

router = APIRouter(prefix="/auth", tags=["auth"])
optional_bearer = HTTPBearer(auto_error=False)

class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=10, max_length=128)
    merchant_id: str
    role: str = "VIEWER"

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post('/register', status_code=201)
def register(payload: RegisterRequest, request: Request, session: Session = Depends(get_db), credentials: HTTPAuthorizationCredentials | None = Depends(optional_bearer), bootstrap_token: str | None = Header(None, alias="X-Bootstrap-Token")):
    current = None
    if credentials:
        current = get_current_user(request, credentials, session)
    role = payload.role.upper()
    if role not in ROLES: raise HTTPException(422, "Invalid role")
    count = session.scalar(select(func.count(User.id))) or 0
    if count == 0:
        if not os.getenv("AUTH_BOOTSTRAP_TOKEN", "") or bootstrap_token != os.getenv("AUTH_BOOTSTRAP_TOKEN", ""):
            raise HTTPException(403, "Controlled bootstrap token required for initial registration")
    elif (not current or current.role != "ADMIN" or payload.merchant_id != current.merchant_id):
        raise HTTPException(403, "Only a same-merchant admin may create users")
    merchant = session.get(Merchant, payload.merchant_id)
    if not merchant: raise HTTPException(404, "Merchant not found")
    if count == 0 and role != "ADMIN": raise HTTPException(400, "Initial user must be ADMIN")
    if session.scalar(select(User).where(User.email == payload.email.lower())): raise HTTPException(409, "User already exists")
    user = User(email=payload.email.lower().strip(), password_hash=hash_password(payload.password), merchant_id=merchant.id, role=role, is_active=True)
    session.add(user)
    session.flush()
    record_event(session, action=AUTH_REGISTER, resource_type="USER", resource_id=user.id, merchant_id=user.merchant_id, actor_user_id=getattr(current, "id", None), actor_role=getattr(current, "role", None), actor_type="USER" if current else "SYSTEM", request_id=getattr(request.state, "request_id", None), ip_address=request.client.host if request.client else None, metadata={"email": user.email, "role": user.role})
    session.commit(); session.refresh(user)
    return {"id":user.id,"email":user.email,"merchant_id":user.merchant_id,"role":user.role,"is_active":user.is_active,"created_at":user.created_at}

@router.post('/login')
def login(payload: LoginRequest, request: Request, session: Session = Depends(get_db)):
    user = session.scalar(select(User).where(User.email == payload.email.lower().strip()))
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        if user:
            record_event(session, action=AUTH_LOGIN_FAILURE, resource_type="USER", resource_id=user.id, merchant_id=user.merchant_id, actor_user_id=user.id, actor_role=user.role, actor_type="USER", request_id=getattr(request.state, "request_id", None), ip_address=request.client.host if request.client else None, outcome="FAILURE", metadata={"reason": "invalid_credentials"})
        else:
            record_event(session, action=AUTH_LOGIN_FAILURE, resource_type="AUTHENTICATION", merchant_id=None, actor_type="SYSTEM_GLOBAL", request_id=getattr(request.state, "request_id", None), ip_address=request.client.host if request.client else None, outcome="FAILURE", metadata={"reason": "invalid_credentials"})
        session.commit()
        raise HTTPException(401, "Invalid email or password", headers={"WWW-Authenticate":"Bearer"})
    token = create_access_token(user)
    record_event(session, action=AUTH_LOGIN_SUCCESS, resource_type="USER", resource_id=user.id, merchant_id=user.merchant_id, actor_user_id=user.id, actor_role=user.role, actor_type="USER", request_id=getattr(request.state, "request_id", None), ip_address=request.client.host if request.client else None, metadata={"method": "credential_login"})
    session.commit()
    return {"access_token": token, "token_type":"bearer", "expires_in": settings.access_token_expire_minutes * 60}

@router.get('/me')
def me(user=Depends(get_current_user)):
    return {"id":user.id,"email":user.email,"merchant_id":user.merchant_id,"role":user.role,"is_active":user.is_active,"created_at":user.created_at}
