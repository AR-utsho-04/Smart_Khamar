from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, Farm, FarmVet, Animal
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not creds:
        raise HTTPException(401, "not_authenticated")
    try:
        data = decode_token(creds.credentials)
        user = db.get(User, int(data["sub"]))
    except Exception:
        raise HTTPException(401, "invalid_token")
    if not user or not user.is_active:
        raise HTTPException(401, "invalid_token")
    return user


def require_role(*roles):
    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "forbidden")
        if user.role == "vet" and not user.is_approved:
            raise HTTPException(403, "vet_not_approved")
        return user
    return dep


def accessible_farm_ids(db: Session, user: User):
    """None = all farms (admin). Otherwise a list of farm ids the user may access."""
    if user.role == "admin":
        return None
    if user.role == "farmer":
        return [f.id for f in db.query(Farm).filter(Farm.owner_id == user.id).all()]
    if not user.is_approved:
        return []
    return [r.farm_id for r in db.query(FarmVet).filter(FarmVet.vet_id == user.id, FarmVet.status == "approved").all()]


def get_farm_checked(db: Session, user: User, farm_id: int) -> Farm:
    ids = accessible_farm_ids(db, user)
    farm = db.get(Farm, farm_id)
    if not farm or (ids is not None and farm_id not in ids):
        raise HTTPException(404, "not_found")
    return farm


def get_animal_checked(db: Session, user: User, animal_id: int) -> Animal:
    a = db.get(Animal, animal_id)
    if not a:
        raise HTTPException(404, "not_found")
    get_farm_checked(db, user, a.farm_id)
    return a
