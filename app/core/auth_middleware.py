from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from datetime import datetime, timezone
import jwt
from app.core.config import settings
from app.core.database import get_db
from app.models.all_models import Profile

bearer_scheme = HTTPBearer()

def get_current_profile(
    credentials: HTTPAuthorizationCredentials = Security(bearer_scheme),
    db: Session = Depends(get_db)
) -> Profile:

    token = credentials.credentials

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido.")

    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Tipo de token incorrecto.")

    profile = db.query(Profile).filter(
        Profile.id == payload.get("sub")
    ).first()

    if not profile:
        raise HTTPException(status_code=401, detail="Usuario no encontrado.")

    return profile