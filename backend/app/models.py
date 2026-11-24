from datetime import datetime, date, timezone
from sqlalchemy import (String, Integer, Float, Boolean, Date, DateTime, Text, ForeignKey, JSON,
                        UniqueConstraint, Index, Table, Column)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def utcnow() -> datetime:
    """Naive UTC datetime (all datetimes are stored as UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(10))  # farmer | vet | admin
    language: Mapped[str] = mapped_column(String(2), default="en")
    license_no: Mapped[str | None] = mapped_column(String(60), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Farm(Base):
    __tablename__ = "farms"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    name: Mapped[str] = mapped_column(String(150))
    district: Mapped[str | None] = mapped_column(String(80), nullable=True)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    species_kept: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class FarmVet(Base):
    __tablename__ = "farm_vets"
    __table_args__ = (UniqueConstraint("farm_id", "vet_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"))
    vet_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | approved | revoked
    granted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Animal(Base):
    __tablename__ = "animals"
    __table_args__ = (UniqueConstraint("farm_id", "tag_no"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    tag_no: Mapped[str] = mapped_column(String(30))
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    species: Mapped[str] = mapped_column(String(10))  # cattle | goat | sheep
    breed: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sex: Mapped[str] = mapped_column(String(6))  # male | female
    dob: Mapped[date | None] = mapped_column(Date, nullable=True)
    age_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="healthy")
    photo_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Symptom(Base):
    __tablename__ = "symptoms"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_bn: Mapped[str] = mapped_column(String(80))


class Disease(Base):
    __tablename__ = "diseases"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(40), unique=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_bn: Mapped[str] = mapped_column(String(80))
    species_applicable: Mapped[str] = mapped_column(String(60), default="cattle,goat,sheep")


record_symptoms = Table(
    "record_symptoms", Base.metadata,
    Column("record_id", ForeignKey("health_records.id"), primary_key=True),
    Column("symptom_id", ForeignKey("symptoms.id"), primary_key=True),
)


class HealthRecord(Base):
    __tablename__ = "health_records"
    __table_args__ = (Index("ix_records_animal_time", "animal_id", "recorded_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"))
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    feed_intake_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    milk_yield_l: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(10), default="manual")  # manual | csv | sensor
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    symptoms: Mapped[list[Symptom]] = relationship(secondary=record_symptoms, lazy="selectin")


class Prediction(Base):
    __tablename__ = "predictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    record_id: Mapped[int] = mapped_column(ForeignKey("health_records.id"))
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), index=True)
    model_version: Mapped[str] = mapped_column(String(40))
    top_predictions: Mapped[list] = mapped_column(JSON)
    risk_level: Mapped[str] = mapped_column(String(10))
    top_factors: Mapped[list] = mapped_column(JSON)
    safety_net_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class PredictionFeedback(Base):
    __tablename__ = "prediction_feedback"
    id: Mapped[int] = mapped_column(primary_key=True)
    prediction_id: Mapped[int] = mapped_column(ForeignKey("predictions.id"), unique=True)
    vet_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    confirmed: Mapped[bool] = mapped_column(Boolean)
    actual_disease_id: Mapped[int | None] = mapped_column(ForeignKey("diseases.id"), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(40))
    severity: Mapped[str] = mapped_column(String(10))
    message_en: Mapped[str] = mapped_column(Text)
    message_bn: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(15), default="open")  # open|acknowledged|snoozed|resolved
    snoozed_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    related_record_id: Mapped[int | None] = mapped_column(ForeignKey("health_records.id"), nullable=True)
    related_prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    acknowledged_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    escalated: Mapped[bool] = mapped_column(Boolean, default=False)


class VaccineSchedule(Base):
    __tablename__ = "vaccine_schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    species: Mapped[str] = mapped_column(String(10), default="all")
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(15), default="vaccination")  # vaccination|deworming|checkup
    interval_days: Mapped[int] = mapped_column(Integer)
    first_dose_age_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[int] = mapped_column(primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), index=True)
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("vaccine_schedules.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(15))  # vaccination|deworming|checkup|follow_up
    title: Mapped[str] = mapped_column(String(150))
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending|done|overdue|cancelled
    notified_7d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_1d: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_overdue: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Consultation(Base):
    __tablename__ = "consultations"
    id: Mapped[int] = mapped_column(primary_key=True)
    animal_id: Mapped[int] = mapped_column(ForeignKey("animals.id"), index=True)
    vet_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    prediction_id: Mapped[int | None] = mapped_column(ForeignKey("predictions.id"), nullable=True)
    diagnosis: Mapped[str] = mapped_column(Text)
    treatment: Mapped[str | None] = mapped_column(Text, nullable=True)
    medicine: Mapped[str | None] = mapped_column(String(150), nullable=True)
    dosage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    follow_up_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class ConsultationComment(Base):
    __tablename__ = "consultation_comments"
    id: Mapped[int] = mapped_column(primary_key=True)
    consultation_id: Mapped[int] = mapped_column(ForeignKey("consultations.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Threshold(Base):
    __tablename__ = "thresholds"
    __table_args__ = (UniqueConstraint("species", "parameter"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    species: Mapped[str] = mapped_column(String(10))  # cattle|goat|sheep|all
    parameter: Mapped[str] = mapped_column(String(40))
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)


class NotificationLog(Base):
    __tablename__ = "notification_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    alert_id: Mapped[int | None] = mapped_column(ForeignKey("alerts.id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(10), default="email")
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10))  # sent|failed|logged
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class Device(Base):
    """An IoT sensor (for example a collar) that sends readings for one animal."""
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    farm_id: Mapped[int] = mapped_column(ForeignKey("farms.id"), index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(80))
    device_uid: Mapped[str] = mapped_column(String(20), unique=True)
    key_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256 of the device key
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    battery_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class SensorReading(Base):
    """One continuous measurement from a device, with the AI anomaly result."""
    __tablename__ = "sensor_readings"
    __table_args__ = (Index("ix_sensor_animal_time", "animal_id", "recorded_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.id"), index=True)
    animal_id: Mapped[int | None] = mapped_column(ForeignKey("animals.id"), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime)
    temperature_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    heart_rate_bpm: Mapped[float | None] = mapped_column(Float, nullable=True)
    activity_index: Mapped[float | None] = mapped_column(Float, nullable=True)
    anomaly_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # lower = more unusual
    is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False)
    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
