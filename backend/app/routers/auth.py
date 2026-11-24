from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import RegisterIn, LoginIn, ProfileIn, PasswordIn
from ..security import hash_password, verify_password, create_token
from ..serializers import user_out
from ..services.common import audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=201)
def register(body: RegisterIn, db: Session = Depends(get_db)):
    email = body.email.strip().lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "email_taken")
    u = User(name=body.name.strip(), email=email, phone=body.phone, password_hash=hash_password(body.password),
             role=body.role, language=body.language, license_no=body.license_no,
             is_approved=(body.role != "vet"))  # new vets wait for admin approval
    db.add(u)
    db.flush()
    audit(db, u, "register", "user", u.id, {"role": u.role})
    db.commit()
    return user_out(u)


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    u = db.query(User).filter(User.email == body.email.strip().lower()).first()
    if not u or not u.is_active or not verify_password(body.password, u.password_hash):
        raise HTTPException(401, "invalid_credentials")
    return {"access_token": create_token(u), "token_type": "bearer", "user": user_out(u)}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me")
def update_me(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is not None:
            setattr(user, k, v)
    db.commit()
    return user_out(user)


@router.post("/change-password")
def change_password(body: PasswordIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "wrong_password")
    user.password_hash = hash_password(body.new_password)
    audit(db, user, "change_password", "user", user.id)
    db.commit()
    return {"ok": True}
