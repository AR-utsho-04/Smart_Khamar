from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str = Field(pattern=EMAIL, max_length=255)
    password: str = Field(min_length=8, max_length=64)
    role: Literal["farmer", "vet"]
    phone: Optional[str] = Field(default=None, max_length=30)
    language: Literal["en", "bn"] = "en"
    license_no: Optional[str] = Field(default=None, max_length=60)


class LoginIn(BaseModel):
    email: str
    password: str


class ProfileIn(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    phone: Optional[str] = Field(default=None, max_length=30)
    language: Optional[Literal["en", "bn"]] = None


class PasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=64)


class FarmIn(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    district: Optional[str] = None
    address: Optional[str] = None
    species_kept: Optional[str] = None


class VetInviteIn(BaseModel):
    vet_email: str


class StatusIn(BaseModel):
    status: str


class AnimalIn(BaseModel):
    farm_id: int
    tag_no: str = Field(min_length=1, max_length=30)
    name: Optional[str] = Field(default=None, max_length=80)
    species: Literal["cattle", "goat", "sheep"]
    breed: Optional[str] = Field(default=None, max_length=80)
    sex: Literal["male", "female"]
    dob: Optional[date] = None
    age_months: Optional[int] = Field(default=None, ge=0, le=400)
    weight_kg: Optional[float] = None


class AnimalUpdate(BaseModel):
    tag_no: Optional[str] = Field(default=None, min_length=1, max_length=30)
    name: Optional[str] = None
    breed: Optional[str] = None
    sex: Optional[Literal["male", "female"]] = None
    dob: Optional[date] = None
    age_months: Optional[int] = Field(default=None, ge=0, le=400)
    weight_kg: Optional[float] = None


class RecordIn(BaseModel):
    recorded_at: Optional[datetime] = None
    temperature_c: Optional[float] = None
    weight_kg: Optional[float] = None
    feed_intake_kg: Optional[float] = None
    milk_yield_l: Optional[float] = None
    symptoms: list[str] = []
    notes: Optional[str] = None


class FeedbackIn(BaseModel):
    confirmed: bool
    actual_disease_key: Optional[str] = None
    comment: Optional[str] = None


class SnoozeIn(BaseModel):
    hours: int = Field(ge=1, le=72)


class ReminderIn(BaseModel):
    type: Literal["vaccination", "deworming", "checkup", "follow_up"]
    title: str = Field(min_length=1, max_length=150)
    due_date: date
    schedule_id: Optional[int] = None


class ReminderPatch(BaseModel):
    status: Optional[Literal["done", "cancelled", "pending"]] = None
    due_date: Optional[date] = None


class ConsultationIn(BaseModel):
    diagnosis: str = Field(min_length=1)
    treatment: Optional[str] = None
    medicine: Optional[str] = None
    dosage: Optional[str] = None
    follow_up_date: Optional[date] = None
    prediction_id: Optional[int] = None


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class ThresholdIn(BaseModel):
    species: Literal["cattle", "goat", "sheep", "all"]
    parameter: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None


class ScheduleIn(BaseModel):
    species: Literal["cattle", "goat", "sheep", "all"] = "all"
    name: str
    kind: Literal["vaccination", "deworming", "checkup"] = "vaccination"
    interval_days: int = Field(gt=0)
    first_dose_age_days: Optional[int] = None
    is_active: bool = True


class LookupIn(BaseModel):
    key: str
    name_en: str
    name_bn: str
    species_applicable: Optional[str] = None


class SensorIn(BaseModel):
    farm_id: int
    tag_no: str
    recorded_at: Optional[datetime] = None
    temperature_c: Optional[float] = None
    weight_kg: Optional[float] = None
    feed_intake_kg: Optional[float] = None
    milk_yield_l: Optional[float] = None


class DeviceIn(BaseModel):
    farm_id: int
    name: str = Field(min_length=1, max_length=80)
    animal_id: Optional[int] = None


class DevicePatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    animal_id: Optional[int] = None  # send null to unassign
    is_active: Optional[bool] = None


class ReadingIn(BaseModel):
    recorded_at: Optional[datetime] = None
    temperature_c: Optional[float] = None
    heart_rate_bpm: Optional[float] = None
    activity_index: Optional[float] = None
    battery_pct: Optional[float] = None


class TelemetryIn(ReadingIn):
    """Either one reading (fields above) or a batch: {"readings": [ ... ]} (max 200)."""
    readings: Optional[list[ReadingIn]] = None
