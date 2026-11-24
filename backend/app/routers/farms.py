from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..deps import require_role, accessible_farm_ids, get_farm_checked, get_current_user
from ..models import Farm, FarmVet, User, utcnow
from ..schemas import FarmIn, VetInviteIn, StatusIn
from ..serializers import farm_out
from ..services.common import audit

router = APIRouter(tags=["farms"])


@router.get("/farms")
def list_farms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ids = accessible_farm_ids(db, user)
    q = db.query(Farm)
    if ids is not None:
        q = q.filter(Farm.id.in_(ids))
    return [farm_out(f) for f in q.order_by(Farm.id).all()]


@router.post("/farms", status_code=201)
def create_farm(body: FarmIn, user: User = Depends(require_role("farmer")), db: Session = Depends(get_db)):
    f = Farm(owner_id=user.id, **body.model_dump())
    db.add(f)
    db.flush()
    audit(db, user, "create", "farm", f.id)
    db.commit()
    return farm_out(f)


@router.get("/farms/{farm_id}")
def get_farm(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return farm_out(get_farm_checked(db, user, farm_id))


@router.put("/farms/{farm_id}")
def update_farm(farm_id: int, body: FarmIn, user: User = Depends(require_role("farmer")), db: Session = Depends(get_db)):
    f = get_farm_checked(db, user, farm_id)
    for k, v in body.model_dump().items():
        setattr(f, k, v)
    db.commit()
    return farm_out(f)


def _owned(db, user, farm_id):
    f = get_farm_checked(db, user, farm_id)
    if f.owner_id != user.id:
        raise HTTPException(404, "not_found")
    return f


@router.post("/farms/{farm_id}/vets", status_code=201)
def invite_vet(farm_id: int, body: VetInviteIn, user: User = Depends(require_role("farmer")), db: Session = Depends(get_db)):
    _owned(db, user, farm_id)
    vet = db.query(User).filter(User.email == body.vet_email.strip().lower(), User.role == "vet",
                                User.is_approved.is_(True), User.is_active.is_(True)).first()
    if not vet:
        raise HTTPException(404, "vet_not_found")
    fv = db.query(FarmVet).filter(FarmVet.farm_id == farm_id, FarmVet.vet_id == vet.id).first()
    if fv and fv.status in ("pending", "approved"):
        raise HTTPException(409, "already_invited")
    if fv:
        fv.status, fv.granted_at = "pending", None
    else:
        fv = FarmVet(farm_id=farm_id, vet_id=vet.id, status="pending")
        db.add(fv)
    audit(db, user, "invite_vet", "farm", farm_id, {"vet_id": vet.id})
    db.commit()
    return {"id": fv.id, "vet_id": vet.id, "vet_name": vet.name, "status": fv.status}


@router.get("/farms/{farm_id}/vets")
def list_farm_vets(farm_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_farm_checked(db, user, farm_id)
    if user.role == "vet":
        raise HTTPException(403, "forbidden")
    out = []
    for fv in db.query(FarmVet).filter(FarmVet.farm_id == farm_id).all():
        v = db.get(User, fv.vet_id)
        out.append({"id": fv.id, "vet_id": v.id, "vet_name": v.name, "vet_email": v.email, "status": fv.status})
    return out


@router.patch("/farms/{farm_id}/vets/{vet_id}")
def revoke_vet(farm_id: int, vet_id: int, body: StatusIn, user: User = Depends(require_role("farmer")), db: Session = Depends(get_db)):
    _owned(db, user, farm_id)
    if body.status != "revoked":
        raise HTTPException(422, "only_revoke_allowed")
    fv = db.query(FarmVet).filter(FarmVet.farm_id == farm_id, FarmVet.vet_id == vet_id).first()
    if not fv:
        raise HTTPException(404, "not_found")
    fv.status = "revoked"
    audit(db, user, "revoke_vet", "farm", farm_id, {"vet_id": vet_id})
    db.commit()
    return {"id": fv.id, "status": fv.status}


@router.get("/vet/invitations")
def my_invitations(user: User = Depends(require_role("vet")), db: Session = Depends(get_db)):
    out = []
    for fv in db.query(FarmVet).filter(FarmVet.vet_id == user.id, FarmVet.status.in_(["pending", "approved"])).all():
        f = db.get(Farm, fv.farm_id)
        owner = db.get(User, f.owner_id)
        out.append({"id": fv.id, "farm_id": f.id, "farm_name": f.name, "district": f.district,
                    "owner_name": owner.name, "status": fv.status})
    return out


@router.patch("/vet/invitations/{inv_id}")
def respond_invitation(inv_id: int, body: StatusIn, user: User = Depends(require_role("vet")), db: Session = Depends(get_db)):
    fv = db.get(FarmVet, inv_id)
    if not fv or fv.vet_id != user.id:
        raise HTTPException(404, "not_found")
    if body.status not in ("approved", "revoked"):
        raise HTTPException(422, "invalid_status")
    fv.status = body.status
    fv.granted_at = utcnow() if body.status == "approved" else None
    audit(db, user, "respond_invitation", "farm", fv.farm_id, {"status": body.status})
    db.commit()
    return {"id": fv.id, "status": fv.status}
