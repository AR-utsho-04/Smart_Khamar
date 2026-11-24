# SPEC.md — AI-Based Livestock Health Monitoring System

> This file is the single source of truth for building the project. Read all of it before writing code.
> Project: SE 231 capstone, Daffodil International University. Target users: small and medium livestock farms in Bangladesh (cattle, goats, sheep).

---

## 0. Instructions to the coding agent

1. Build in the **phases listed in Section 17**, in order. Finish a phase and meet its acceptance criteria before starting the next.
2. Use **only the technologies in Section 2**. Do not swap frameworks or add major libraries without writing the reason in `ASSUMPTIONS.md`.
3. Use the **exact table names, column names, enum values, endpoint paths, and JSON field names** in this file.
4. Where this spec is silent, make the simplest reasonable choice and record it in `ASSUMPTIONS.md`. Do not stop to ask questions.
5. Do not build anything in Section 18 (out of scope).
6. After each phase: run the tests, fix failures, and write a short summary of what was built and how to run it in `README.md`.
7. Every user-visible string must exist in both English and Bangla (Section 14.4). Never hard-code UI text in components.
8. The AI predicts risk and supports a veterinarian. It never gives a final diagnosis. Show this disclaimer wherever predictions appear (Section 14.5).
9. Never store plain-text passwords. Never expose password hashes in any API response.

---

## 1. Product summary

A web application where:
- **Farmers** register animals and log health data (form or CSV).
- An **AI model** estimates disease risk and shows a confidence score.
- An **automation engine** creates alerts for abnormal readings and sends reminders for vaccination, deworming, and checkups (dashboard + email).
- **Veterinarians** review cases on farms that granted them access, and record diagnosis and treatment.
- **Admins** manage users, vet approvals, thresholds, and lookup lists.
- The interface supports **Bangla and English** and is **mobile-responsive**.

Roles: `farmer`, `vet`, `admin`.

---

## 2. Fixed technology decisions

| Layer | Choice |
| --- | --- |
| Frontend | React 18 + Vite, JavaScript (JSX), Tailwind CSS, React Router v6, axios, react-hook-form, recharts, react-i18next, react-hot-toast, lucide-react, dayjs |
| Backend | Python 3.11+, FastAPI, Uvicorn, Pydantic v2, SQLAlchemy 2.x, Alembic |
| Database | SQLite for local development, PostgreSQL supported. Selected only by `DATABASE_URL`. Code must work on both. |
| Auth | JWT (HS256) access tokens, passwords hashed with bcrypt (passlib) |
| AI/ML | scikit-learn, pandas, numpy, joblib |
| Scheduler | APScheduler (BackgroundScheduler), started inside the FastAPI app on startup |
| Email | `smtplib` via a small service; when SMTP is not configured, log emails to console and database instead of sending |
| PDF reports | reportlab, with the Noto Sans Bengali TTF registered so Bangla text renders |
| Backend tests | pytest + httpx (FastAPI TestClient) |

Do not use Celery or Redis in the first version.

---

## 3. Repository structure

```
livestock-health/
├── SPEC.md
├── README.md
├── ASSUMPTIONS.md
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── alembic.ini
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── security.py            # hashing, JWT
│   │   ├── deps.py                # get_db, get_current_user, require_role, farm access checks
│   │   ├── models/                # SQLAlchemy models (one file per entity group)
│   │   ├── schemas/               # Pydantic schemas
│   │   ├── routers/               # auth, farms, animals, records, predictions, alerts,
│   │   │                          # reminders, consultations, dashboard, reports, admin, readings
│   │   ├── services/              # business logic: records, rules, alerts, reminders,
│   │   │                          # prediction, email, reports, csv_import
│   │   ├── ml/
│   │   │   ├── generate_data.py   # synthetic data generator
│   │   │   ├── train.py           # training + evaluation script
│   │   │   ├── predict.py         # load model, predict, explain
│   │   │   ├── features.py        # feature building shared by train and predict
│   │   │   └── artifacts/         # model.joblib, metrics.json (created by train.py)
│   │   ├── scheduler/jobs.py
│   │   ├── i18n/messages.py       # bilingual alert/email templates
│   │   └── assets/fonts/          # NotoSansBengali-Regular.ttf, NotoSansBengali-Bold.ttf
│   ├── scripts/seed.py
│   └── tests/
├── frontend/
│   ├── package.json
│   ├── vite.config.js             # dev proxy /api -> http://localhost:8000
│   └── src/
│       ├── main.jsx, App.jsx
│       ├── api/                   # axios client + one file per resource
│       ├── context/               # AuthContext
│       ├── components/            # shared UI
│       ├── pages/                 # one folder per role: farmer/, vet/, admin/, public/
│       ├── i18n/                  # en.json, bn.json, index.js
│       └── utils/
└── data/
    └── sample_health_data.csv     # sample CSV for import demo
```

---

## 4. Configuration (`backend/.env.example`)

```
DATABASE_URL=sqlite:///./livestock.db
SECRET_KEY=change-me
ACCESS_TOKEN_EXPIRE_MINUTES=480
CORS_ORIGINS=http://localhost:5173
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=alerts@example.com
SCHEDULER_ENABLED=true
SENSOR_API_KEY=dev-sensor-key
```

If `SMTP_HOST` is empty, the email service writes the email to `notification_log` with `status="logged"` and prints it to the console.

---

## 5. Data model

Use SQLAlchemy 2.x declarative models. All tables have `id` (integer primary key, autoincrement) unless stated. Timestamps are timezone-aware UTC (`DateTime(timezone=True)`). Use `created_at` default now.

### 5.1 Tables

**users**
- `id`, `name` str(120) not null, `email` str(255) unique not null, `phone` str(30) null
- `password_hash` str not null, `role` enum(`farmer`,`vet`,`admin`) not null
- `language` enum(`en`,`bn`) default `en`
- `license_no` str(60) null (vets only)
- `is_active` bool default true
- `is_approved` bool default true (farmers/admin) and **false for new vets** until admin approves
- `created_at`

**farms**
- `id`, `owner_id` FK users.id not null, `name` str(150) not null
- `district` str(80) null, `address` str(255) null, `species_kept` str(100) null (comma list)
- `created_at`

**farm_vets** (vet access to a farm)
- `id`, `farm_id` FK farms.id, `vet_id` FK users.id
- `status` enum(`pending`,`approved`,`revoked`) default `pending`
- `granted_at` null
- unique(`farm_id`,`vet_id`)

**animals**
- `id`, `farm_id` FK farms.id not null
- `tag_no` str(30) not null, unique per farm (unique(`farm_id`,`tag_no`))
- `name` str(80) null
- `species` enum(`cattle`,`goat`,`sheep`) not null
- `breed` str(80) null, `sex` enum(`male`,`female`) not null
- `dob` date null, `age_months` int null (used if dob unknown)
- `weight_kg` float null (latest known)
- `status` enum(`healthy`,`under_observation`,`sick`,`recovered`,`sold`,`deceased`) default `healthy`
- `photo_url` str null
- `is_archived` bool default false
- `created_at`, `updated_at`

**symptoms** (lookup)
- `id`, `key` str(40) unique, `name_en`, `name_bn`

**diseases** (lookup)
- `id`, `key` str(40) unique, `name_en`, `name_bn`, `species_applicable` str (comma list)

**health_records**
- `id`, `animal_id` FK animals.id not null, `recorded_by` FK users.id not null
- `recorded_at` datetime not null (default now)
- `temperature_c` float null, `weight_kg` float null, `feed_intake_kg` float null, `milk_yield_l` float null
- `notes` text null, `source` enum(`manual`,`csv`,`sensor`) default `manual`
- `created_at`
- Index on (`animal_id`,`recorded_at`)

**record_symptoms**
- `record_id` FK health_records.id, `symptom_id` FK symptoms.id, primary key (`record_id`,`symptom_id`)

**predictions**
- `id`, `record_id` FK health_records.id not null, `animal_id` FK animals.id not null
- `model_version` str(40) not null
- `top_predictions` JSON not null (list of `{disease_key, probability}`, top 3, sorted desc)
- `risk_level` enum(`low`,`medium`,`high`) not null
- `top_factors` JSON not null (list of `{feature, label_en, label_bn, impact}`)
- `safety_net_triggered` bool default false
- `created_at`

**prediction_feedback**
- `id`, `prediction_id` FK predictions.id unique, `vet_id` FK users.id
- `confirmed` bool not null, `actual_disease_id` FK diseases.id null, `comment` text null, `created_at`

**alerts**
- `id`, `farm_id` FK farms.id not null, `animal_id` FK animals.id null
- `type` enum: `fever`,`weight_loss`,`appetite_drop`,`high_risk_prediction`,`critical_safety_net`,`vaccination_due`,`vaccination_overdue`,`missed_entry`,`unacknowledged_escalation`,`follow_up_due`
- `severity` enum(`low`,`medium`,`high`) not null
- `message_en` text not null, `message_bn` text not null
- `status` enum(`open`,`acknowledged`,`snoozed`,`resolved`) default `open`
- `snoozed_until` datetime null
- `related_record_id` FK health_records.id null, `related_prediction_id` FK predictions.id null
- `created_at`, `acknowledged_by` FK users.id null, `acknowledged_at` null
- `escalated` bool default false

**vaccine_schedules** (templates)
- `id`, `species` enum or `all`, `name` str(100), `kind` enum(`vaccination`,`deworming`,`checkup`)
- `interval_days` int not null, `first_dose_age_days` int null, `is_active` bool default true

**reminders**
- `id`, `animal_id` FK animals.id not null, `schedule_id` FK vaccine_schedules.id null
- `type` enum(`vaccination`,`deworming`,`checkup`,`follow_up`), `title` str(150)
- `due_date` date not null
- `status` enum(`pending`,`done`,`overdue`,`cancelled`) default `pending`
- `notified_7d` bool, `notified_1d` bool, `notified_overdue` bool (all default false)
- `completed_at` null, `created_at`

**consultations**
- `id`, `animal_id` FK animals.id, `vet_id` FK users.id, `prediction_id` FK predictions.id null
- `diagnosis` text not null, `treatment` text null, `medicine` str(150) null, `dosage` str(100) null
- `follow_up_date` date null, `created_at`

**consultation_comments**
- `id`, `consultation_id` FK, `user_id` FK users.id, `body` text not null, `created_at`

**thresholds** (admin-editable)
- `id`, `species` enum(`cattle`,`goat`,`sheep`,`all`), `parameter` str(40), `min_value` float null, `max_value` float null
- unique(`species`,`parameter`)

**notification_log**
- `id`, `user_id` FK users.id, `alert_id` FK alerts.id null, `channel` enum(`email`)
- `subject` str, `body` text, `status` enum(`sent`,`failed`,`logged`), `error` text null, `created_at`

**audit_log**
- `id`, `user_id` FK users.id null, `action` str(60), `entity` str(40), `entity_id` int null, `detail` JSON null, `created_at`

### 5.2 Relationships (summary)
- farm 1—N animals; animal 1—N health_records, predictions, reminders, consultations, alerts
- health_record N—N symptoms through record_symptoms
- farm N—N vets through farm_vets
- prediction 1—0..1 prediction_feedback

---

## 6. Constants and enums

**Symptom keys** (seed with Bangla names):

| key | name_en | name_bn |
| --- | --- | --- |
| fever | Fever | জ্বর |
| loss_of_appetite | Loss of appetite | খাওয়া কমে যাওয়া |
| nasal_discharge | Nasal discharge | নাক দিয়ে স্রাব পড়া |
| mouth_lesions | Mouth lesions or drooling | মুখে ঘা বা লালা পড়া |
| lameness | Lameness | খোঁড়ানো |
| skin_nodules | Skin nodules | চামড়ায় গুটি |
| diarrhea | Diarrhea | পাতলা পায়খানা |
| cough | Cough | কাশি |
| swollen_udder | Swollen udder | ওলান ফোলা |
| eye_discharge | Eye discharge | চোখ দিয়ে পানি পড়া |
| weakness | Weakness | দুর্বলতা |
| reduced_milk_yield | Reduced milk yield | দুধ কমে যাওয়া |

**Disease keys** (seed):

| key | name_en | name_bn | species |
| --- | --- | --- | --- |
| healthy | Healthy | সুস্থ | cattle,goat,sheep |
| fmd | Foot-and-Mouth Disease | ক্ষুরা রোগ | cattle,goat,sheep |
| lsd | Lumpy Skin Disease | লাম্পি স্কিন ডিজিজ | cattle |
| mastitis | Mastitis | ওলান প্রদাহ | cattle,goat,sheep |
| bef | Bovine Ephemeral Fever | তিন দিনের জ্বর | cattle |
| ppr | PPR | পিপিআর | goat,sheep |
| pox | Goat/Sheep Pox | ছাগল ও ভেড়ার বসন্ত | goat,sheep |
| parasites | Internal Parasites | অভ্যন্তরীণ পরজীবী | cattle,goat,sheep |

> Note: Bangla translations and disease list are a starting point. They should be reviewed by a native speaker and a veterinarian.

**Risk levels:** `low`, `medium`, `high`. **Severity:** same values.

---

## 7. Authentication and permissions

### 7.1 Auth rules
- `POST /api/v1/auth/register` creates `farmer` or `vet` only. Admin accounts come from the seed script.
- New vets: `is_approved=false`. They can log in but get `403` with `detail="vet_not_approved"` on all vet endpoints until approved.
- Password: minimum 8 characters.
- Token payload: `sub` (user id), `role`, `exp`.
- Every protected endpoint uses a `get_current_user` dependency. Role checks use `require_role("farmer","admin")`-style dependencies.

### 7.2 Access rules (enforce in the service/dependency layer, not only the frontend)
- **Farmer:** can access only farms where `farms.owner_id == user.id` and everything under them.
- **Vet:** can access a farm only if an approved `farm_vets` row exists. Vets can read animals, records, predictions, alerts; create health records; create consultations and prediction feedback. Vets cannot edit or delete animals.
- **Admin:** read access to all farms; manages users, vets, thresholds, lookups, schedules, audit log. Admin does not create health records or consultations.
- Wrong role: `403`. Resource not found or no access to it: `404` (do not reveal existence).

### 7.3 Permission matrix

| Action | farmer | vet | admin |
| --- | --- | --- | --- |
| Manage farms and animals | own | no | all (read) |
| Create health records | own | assigned | no |
| View predictions | own | assigned | all |
| Prediction feedback | no | assigned | no |
| Create consultations | no | assigned | no |
| Grant or revoke vet access | own farm | no | no |
| Acknowledge alerts | own | assigned | all |
| Manage users, thresholds, lookups | no | no | yes |

---

## 8. API contract

Base path: `/api/v1`. JSON requests and responses. Dates ISO 8601. Authorization: `Authorization: Bearer <token>`.

**Error format (all errors):**
```json
{ "detail": "human_readable_or_code", "errors": [ { "field": "temperature_c", "message": "must be between 35 and 43" } ] }
```
`errors` is optional and used for validation errors (HTTP 422) and CSV import.

**Pagination** for list endpoints: query `page` (default 1), `page_size` (default 20, max 100). Response:
```json
{ "items": [ ... ], "total": 57, "page": 1, "page_size": 20 }
```

### 8.1 Auth
| Method | Path | Body / notes | Response |
| --- | --- | --- | --- |
| POST | `/auth/register` | `{name,email,password,role,phone?,language?,license_no?}` | user object |
| POST | `/auth/login` | `{email,password}` | `{access_token, token_type:"bearer", user}` |
| GET | `/auth/me` | | user object |
| PATCH | `/auth/me` | `{name?,phone?,language?}` | user object |
| POST | `/auth/change-password` | `{old_password,new_password}` | `{ok:true}` |

User object: `{id,name,email,phone,role,language,is_approved,is_active}`.

### 8.2 Farms and vet access
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/farms` | farmer: own; vet: approved; admin: all |
| POST | `/farms` | farmer only. `{name,district?,address?,species_kept?}` |
| GET/PUT | `/farms/{id}` | |
| POST | `/farms/{id}/vets` | farmer invites a vet. Body `{vet_email}`. Creates `farm_vets` with `pending`. Vet must exist, be approved. |
| GET | `/farms/{id}/vets` | list with status |
| PATCH | `/farms/{id}/vets/{vet_id}` | farmer sets `{status:"approved"|"revoked"}` |
| GET | `/vet/invitations` | vet sees own pending invitations |
| PATCH | `/vet/invitations/{farm_vet_id}` | vet accepts: `{status:"approved"}` or declines: `{status:"revoked"}` |

Access becomes active only when status is `approved` by **both** steps: the farmer's invitation sets `pending`, and the vet's acceptance sets `approved`. (Simplest implementation: farmer invites → `pending`; vet accepts → `approved`; farmer can revoke anytime.)

### 8.3 Animals
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/animals` | filters: `farm_id`, `species`, `status`, `q` (search tag_no or name), `include_archived` |
| POST | `/animals` | farmer. `{farm_id,tag_no,name?,species,breed?,sex,dob?,age_months?,weight_kg?}` |
| GET | `/animals/{id}` | includes latest record and latest prediction summary |
| PUT | `/animals/{id}` | farmer |
| DELETE | `/animals/{id}` | soft delete: sets `is_archived=true` |
| PATCH | `/animals/{id}/status` | `{status}`; farmer or vet |
| GET | `/animals/{id}/timeline` | merged, newest first: records, predictions, consultations, reminders done, alerts. Each item: `{type, at, summary, ref_id}` |

### 8.4 Health records and CSV import
| Method | Path | Notes |
| --- | --- | --- |
| POST | `/animals/{id}/records` | body below. **Triggers the record pipeline (Section 9.4)** and returns the created record plus prediction and alerts |
| GET | `/animals/{id}/records` | paginated, newest first, filter `from`,`to` |
| GET | `/records/{id}` | |
| POST | `/records/import` | multipart: `file` (CSV), `farm_id`. Returns import report |

Record create body:
```json
{
  "recorded_at": "2026-11-16T09:30:00Z",
  "temperature_c": 40.1,
  "weight_kg": 312.5,
  "feed_intake_kg": 6.0,
  "milk_yield_l": 8.5,
  "symptoms": ["fever", "loss_of_appetite"],
  "notes": "Standing apart from herd"
}
```
All measurement fields are optional, but **at least one measurement or one symptom is required**.

Record create response:
```json
{
  "record": { "id": 101, "animal_id": 7, "...": "..." },
  "prediction": {
    "id": 55,
    "model_version": "v1",
    "risk_level": "high",
    "top_predictions": [
      { "disease_key": "fmd", "name_en": "Foot-and-Mouth Disease", "name_bn": "ক্ষুরা রোগ", "probability": 0.71 },
      { "disease_key": "bef", "name_en": "Bovine Ephemeral Fever", "name_bn": "তিন দিনের জ্বর", "probability": 0.14 },
      { "disease_key": "healthy", "name_en": "Healthy", "name_bn": "সুস্থ", "probability": 0.06 }
    ],
    "top_factors": [ { "feature": "temperature_c", "label_en": "High temperature", "label_bn": "উচ্চ তাপমাত্রা", "impact": 0.32 } ],
    "safety_net_triggered": false
  },
  "alerts": [ { "id": 12, "type": "high_risk_prediction", "severity": "high" } ]
}
```

**CSV import format** (UTF-8, header row required, max 5000 rows, max 2 MB):
```
tag_no,recorded_at,temperature_c,weight_kg,feed_intake_kg,milk_yield_l,symptoms,notes
C-001,2026-11-10,38.7,310,8.2,12.0,,
C-002,2026-11-10T08:00:00,40.3,295,3.1,4.0,fever;loss_of_appetite,off feed
```
- `tag_no` must match an animal in the given `farm_id`.
- `symptoms` is a semicolon-separated list of symptom keys.
- Valid rows are imported (each runs the full record pipeline); invalid rows are skipped.

Import report:
```json
{ "total_rows": 50, "imported": 47, "failed": 3,
  "errors": [ { "row": 12, "field": "tag_no", "message": "animal not found" } ] }
```

### 8.5 Predictions
| Method | Path | Notes |
| --- | --- | --- |
| POST | `/records/{id}/predict` | re-run prediction for an existing record |
| GET | `/animals/{id}/predictions` | paginated |
| GET | `/predictions/{id}` | |
| POST | `/predictions/{id}/feedback` | vet only. `{confirmed, actual_disease_key?, comment?}` |

### 8.6 Alerts
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/alerts` | filters: `status`, `severity`, `farm_id`, `animal_id`. Farmer sees own farms; vet sees only `high` severity on approved farms; admin all |
| GET | `/alerts/summary` | counts by severity for open alerts |
| PATCH | `/alerts/{id}/acknowledge` | sets `acknowledged` |
| PATCH | `/alerts/{id}/snooze` | `{hours: 1..72}` |
| PATCH | `/alerts/{id}/resolve` | |

### 8.7 Reminders
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/reminders` | filters: `status`, `animal_id`, `farm_id`, `from`, `to` |
| POST | `/animals/{id}/reminders` | `{type,title,due_date,schedule_id?}` |
| PATCH | `/reminders/{id}` | `{status:"done"|"cancelled"}` or change `due_date` |
| POST | `/animals/{id}/reminders/generate` | creates reminders from active `vaccine_schedules` for the animal's species (skip duplicates) |

When a reminder is marked `done` and it came from a schedule, **create the next reminder** at `completed date + interval_days`.

### 8.8 Consultations
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/consultations` | vet: own; farmer: own farm animals; filters `animal_id`, `farm_id` |
| GET | `/consultations/queue` | vet only. Animals on approved farms that are `sick` or `under_observation`, or have an open high alert, ordered by severity then time |
| POST | `/animals/{id}/consultations` | vet. `{diagnosis,treatment?,medicine?,dosage?,follow_up_date?,prediction_id?}`. If `follow_up_date` is set, create a reminder of type `follow_up` |
| GET | `/consultations/{id}` | includes comments |
| POST | `/consultations/{id}/comments` | farmer (own animal) or vet |

### 8.9 Dashboard and reports
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/dashboard/summary` | query `farm_id?`, `from?`, `to?` (default last 30 days) |
| GET | `/reports/herd` | `farm_id`, `from`, `to`, `format=pdf|csv` |
| GET | `/reports/animal/{id}` | `format=pdf` (animal health card) |
| GET | `/reports/vaccinations-due` | `farm_id`, `format=pdf|csv` |
| GET | `/reports/treatments` | `farm_id`, `from`, `to`, `format=csv` |

Dashboard summary response:
```json
{
  "animals_total": 42,
  "animals_by_species": { "cattle": 20, "goat": 15, "sheep": 7 },
  "animals_by_status": { "healthy": 35, "under_observation": 4, "sick": 3 },
  "open_alerts_by_severity": { "high": 2, "medium": 5, "low": 3 },
  "risk_distribution": { "low": 30, "medium": 8, "high": 4 },
  "disease_cases_over_time": [ { "date": "2026-11-01", "fmd": 1, "lsd": 0, "ppr": 2 } ],
  "temperature_trend": [ { "date": "2026-11-01", "avg_temp": 38.9 } ],
  "vaccination_coverage_pct": 78.5,
  "upcoming_reminders": [ { "id": 3, "animal_tag": "C-001", "title": "FMD vaccination", "due_date": "2026-11-20" } ]
}
```
`risk_distribution` counts each animal's **latest** prediction risk level. `vaccination_coverage_pct` = animals with no overdue vaccination reminder ÷ active animals × 100.

### 8.10 Admin
| Method | Path | Notes |
| --- | --- | --- |
| GET | `/admin/users` | filters `role`, `is_approved`, `q` |
| PATCH | `/admin/users/{id}` | `{is_active?}` |
| PATCH | `/admin/vets/{id}/approve` | sets `is_approved=true` |
| GET/PUT | `/admin/thresholds` | list; PUT replaces values per (species, parameter) |
| CRUD | `/admin/schedules` | vaccine_schedules |
| CRUD | `/admin/symptoms`, `/admin/diseases` | lookups |
| GET | `/admin/audit-log` | paginated |
| GET | `/admin/model` | current model version and metrics from `metrics.json` |

### 8.11 Sensor-ready endpoint (no hardware needed)
`POST /api/v1/readings` with header `X-API-Key: <SENSOR_API_KEY>`. Body: `{farm_id, tag_no, recorded_at?, temperature_c?, weight_kg?, feed_intake_kg?, milk_yield_l?}`. Creates a record with `source="sensor"` and runs the normal pipeline.

### 8.12 Health check
`GET /health` returns `{status:"ok"}` (no auth, not under `/api/v1`).

---

## 9. Business rules

### 9.1 Validation ranges (reject with 422 if outside)
| Field | Range |
| --- | --- |
| temperature_c | 35.0 to 43.0 |
| weight_kg | cattle 20–1200, goat 2–120, sheep 2–150 |
| feed_intake_kg | 0 to 60 |
| milk_yield_l | 0 to 60 |
| symptoms | each must be a known symptom key |
| recorded_at | not more than 5 minutes in the future |

### 9.2 Default thresholds (seed into `thresholds`; admin editable)
These are approximate starting values. They must be reviewed by a veterinarian.

| species | parameter | min | max |
| --- | --- | --- | --- |
| cattle | temperature_c | 38.0 | 39.5 |
| goat | temperature_c | 38.5 | 40.0 |
| sheep | temperature_c | 38.5 | 40.0 |
| all | weight_drop_pct_7d | null | 5 |
| all | feed_drop_pct | null | 30 |
| all | risk_medium_cutoff | 0.30 | null |
| all | risk_high_cutoff | 0.60 | null |
| all | missed_entry_days | null | 2 |
| all | escalation_hours | null | 6 |
| all | fever_high_margin_c | null | 1.0 |

### 9.3 Derived values (computed when a record is saved)
- `weight_change_pct_7d` = (weight_now − weight of the most recent record 5–9 days ago) ÷ that weight × 100. If no such record, use `0`.
- `feed_change_pct` = (feed_now − average feed of records in the previous 7 days) ÷ that average × 100. If no history or feed missing, use `0`.
- Also update `animals.weight_kg` when a record includes `weight_kg`.

### 9.4 Record pipeline (runs for every new record, any source)
1. Validate input and check access.
2. Save `health_records` and `record_symptoms`.
3. Compute derived values.
4. Run **rule checks** (9.5) → create alerts.
5. Run **ML prediction** (Section 10) and save `predictions`.
6. Apply **risk level** and **safety net** (9.6).
7. If risk is `high` → create `high_risk_prediction` alert. If safety net triggered → create `critical_safety_net` alert.
8. Update animal status (9.7).
9. For every new alert: send an email notification (Section 12) to the farm owner; for `high` severity also to all approved vets of the farm.
10. Return the response from Section 8.4.

### 9.5 Rule checks
| Alert type | Condition | Severity |
| --- | --- | --- |
| fever | temperature above species max | `medium`; `high` if above max + `fever_high_margin_c` |
| weight_loss | `weight_change_pct_7d` ≤ −`weight_drop_pct_7d` | medium |
| appetite_drop | `feed_change_pct` ≤ −`feed_drop_pct` | medium |

**De-duplication:** do not create a new alert if an alert of the same `type` for the same animal is still `open` or `acknowledged` and was created within the last 24 hours.

### 9.6 Risk level and safety net
- `p_disease` = highest probability among non-`healthy` classes.
- `risk_level` = `high` if `p_disease ≥ risk_high_cutoff`; `medium` if `≥ risk_medium_cutoff`; else `low`.
- **Safety net:** if temperature > species max + `fever_high_margin_c` **and** at least 2 of these symptoms are present: `mouth_lesions`, `skin_nodules`, `nasal_discharge`, `lameness`, `diarrhea`, `swollen_udder` → force `risk_level="high"` and `safety_net_triggered=true`, regardless of the model.

### 9.7 Animal status updates
- `high` risk and status in (`healthy`,`recovered`,`under_observation`) → set `sick`.
- `medium` risk and status in (`healthy`,`recovered`) → set `under_observation`.
- Never change `sold` or `deceased` automatically.
- Vets and farmers can set status manually (`PATCH /animals/{id}/status`).

### 9.8 Reminders
- Daily job creates `overdue` status when `due_date < today` and status is `pending`.
- Notification points per reminder: 7 days before (`notified_7d`), 1 day before (`notified_1d`), and once when overdue (`notified_overdue`). Each creates an alert (`vaccination_due` low, or `vaccination_overdue` medium) and an email. Use type `follow_up_due` for follow-up reminders.
- On animal creation, the frontend offers a button "Generate reminders", which calls `/animals/{id}/reminders/generate`.

### 9.9 Escalation
Every 30 minutes: any `high` alert with status `open` older than `escalation_hours` and `escalated=false` → set `escalated=true`, create an `unacknowledged_escalation` alert (severity high), and email approved vets.

### 9.10 Missed entry
Daily: for animals with status `under_observation` or `sick` and no record in the last `missed_entry_days` days → create a `missed_entry` alert (low), with de-duplication.

### 9.11 Snooze
Snoozed alerts are hidden from the "open" count until `snoozed_until` passes; a job (every 10 min) sets them back to `open`.

### 9.12 Bilingual messages
All alert `message_en` and `message_bn` come from templates in `i18n/messages.py` with placeholders (animal tag, values, due date). Both languages are stored on the alert; the frontend shows the one matching the user's language. Example:
- `fever` en: `Animal {tag}: temperature {value}°C is above the normal range ({max}°C).`
- `fever` bn: `পশু {tag}: তাপমাত্রা {value}°C স্বাভাবিক সীমার ({max}°C) বেশি।`
- `vaccination_due` en: `Animal {tag}: {title} is due on {date}.`
- `vaccination_due` bn: `পশু {tag}: {title} এর তারিখ {date}।`

Write templates for every alert type in both languages.

---

## 10. AI/ML specification

### 10.1 Task
Multi-class classification. Classes = disease keys from Section 6 (including `healthy`). Output: probabilities for all classes.

### 10.2 Features (exact order, defined once in `ml/features.py` and used by both train and predict)
| Feature | Type |
| --- | --- |
| species | categorical: cattle, goat, sheep (one-hot) |
| sex | categorical (one-hot) |
| age_months | numeric (impute median if missing) |
| temperature_c | numeric (impute species median if missing, add `temp_missing` flag) |
| weight_change_pct_7d | numeric |
| feed_change_pct | numeric |
| 12 symptom flags | binary 0/1, one column per symptom key |
| temp_above_max | numeric: temperature − species max (0 if below) |

Use a scikit-learn `ColumnTransformer` + `Pipeline` so preprocessing is saved with the model.

### 10.3 Synthetic data generator (`ml/generate_data.py`)
Because real labeled data is limited, generate synthetic data for development and demo. Generate **about 6000 rows** (approximately balanced across classes, species restricted to those applicable to each disease). Each row: pick disease → pick an applicable species → sample age, sex → sample temperature from the Normal distribution below → sample each symptom as Bernoulli with the given probability → sample `weight_change_pct_7d` and `feed_change_pct`. Add 5% label noise and random missing values (temperature missing in 3% of rows) to avoid trivially perfect scores.

| disease | temp mean, sd | symptom probabilities | weight_change_pct_7d (mean, sd) | feed_change_pct (mean, sd) |
| --- | --- | --- | --- | --- |
| healthy | species normal: cattle 38.6, goat/sheep 39.2; sd 0.3 | every symptom 0.03 | 0, 1.5 | 0, 10 |
| fmd | 40.2, 0.5 | mouth_lesions 0.9, lameness 0.7, loss_of_appetite 0.9, reduced_milk_yield 0.6, weakness 0.5, fever 0.8 | −3, 2 | −45, 15 |
| lsd | 40.0, 0.5 | skin_nodules 0.95, nasal_discharge 0.5, eye_discharge 0.5, loss_of_appetite 0.7, reduced_milk_yield 0.7, lameness 0.3, fever 0.8 | −3, 2 | −35, 15 |
| mastitis | 39.8, 0.5 | swollen_udder 0.95, reduced_milk_yield 0.9, loss_of_appetite 0.4, fever 0.6 | −1, 1.5 | −20, 12 |
| bef | 40.5, 0.5 | lameness 0.8, weakness 0.7, loss_of_appetite 0.8, nasal_discharge 0.4, reduced_milk_yield 0.7, fever 0.9 | −2, 2 | −40, 15 |
| ppr | 41.0, 0.5 | nasal_discharge 0.9, eye_discharge 0.8, mouth_lesions 0.7, diarrhea 0.7, cough 0.6, loss_of_appetite 0.9, fever 0.9 | −4, 2 | −50, 15 |
| pox | 40.5, 0.5 | skin_nodules 0.95, nasal_discharge 0.5, eye_discharge 0.4, loss_of_appetite 0.7, fever 0.8 | −3, 2 | −35, 15 |
| parasites | 39.3, 0.4 | diarrhea 0.8, weakness 0.7, loss_of_appetite 0.5 | −5, 3 | −15, 10 |

Any symptom not listed for a disease has probability 0.05. These profiles are **simplified demo assumptions**, not clinical data. Put a comment in the file saying they must be replaced or validated with real veterinary data.

Also write `data/sample_health_data.csv` (Section 8.4 format) with about 60 rows across the seeded animals.

### 10.4 Training (`ml/train.py`)
1. Generate (or load) the dataset.
2. Stratified train/test split 80/20, `random_state=42`.
3. Train three models with the preprocessing pipeline: Logistic Regression (max_iter 1000), Random Forest (300 trees), Gradient Boosting.
4. 5-fold stratified cross-validation on the training set; compare by **macro F1**.
5. Pick the best by macro F1. Calibrate probabilities with `CalibratedClassifierCV` (sigmoid, cv=3).
6. Evaluate on the test set: accuracy, macro precision, macro recall, macro F1, per-class report, confusion matrix.
7. Save `ml/artifacts/model.joblib` (pipeline + class list + feature names + model_version `"v1"`) and `ml/artifacts/metrics.json` (all numbers above for all three models, the chosen model name, training date, dataset size and whether the data is synthetic).
8. Print a comparison table.

`python -m app.ml.train` must run end to end in under a few minutes on a normal laptop.

### 10.5 Prediction (`ml/predict.py`)
- Load the model once at application startup (lazy-load on first call if the file exists; if missing, the API still works and returns `503` with `detail="model_not_trained"` for prediction endpoints while record saving continues without a prediction).
- `predict(record, animal, derived) -> { top_predictions (top 3, probability rounded to 2 decimals), probabilities (all classes), top_factors }`.
- **Species filter:** set the probability of diseases not applicable to the animal's species to 0 and renormalize.
- **Explanation (`top_factors`):** return the 3 most influential factors for this prediction. Use the model's feature importances (or logistic coefficients) multiplied by the standardized feature value, restricted to features that are "active" (e.g., present symptom, elevated temperature). Each factor: `{feature, label_en, label_bn, impact}`.
- Log model version on every prediction.

### 10.6 Feedback loop
Vet feedback is stored in `prediction_feedback`. Provide a script `python -m app.ml.export_feedback` that writes confirmed cases to `data/feedback_labeled.csv` for future retraining. (Automatic retraining is out of scope.)

---

## 11. Scheduler jobs (APScheduler, in `scheduler/jobs.py`)

Start in the FastAPI `lifespan` startup if `SCHEDULER_ENABLED=true`. Each job opens its own DB session, is idempotent, and logs what it did.

| Job | Schedule | Action |
| --- | --- | --- |
| reminders_daily | every day 06:00 | mark overdue; send 7-day, 1-day, overdue notifications |
| missed_entry_daily | every day 07:00 | create missed-entry alerts (9.10) |
| escalation_check | every 30 min | escalate unacknowledged high alerts (9.9) |
| snooze_reactivate | every 10 min | reopen expired snoozes (9.11) |

Also provide a protected admin endpoint `POST /api/v1/admin/jobs/run?name=reminders_daily` so jobs can be triggered during a demo.

---

## 12. Email

- `services/email.py` function `send_email(user, subject, body, alert_id=None)`.
- Language: use the recipient's `language`.
- Plain-text body with: alert message, animal tag, farm name, link to the animal page (`FRONTEND_URL` + path), and the AI disclaimer if it concerns a prediction.
- Always write a `notification_log` row. If SMTP is not configured → status `logged` and console print. On SMTP error → status `failed` with `error`; do not crash the request. Retry failed emails once in the next scheduler tick (optional).

---

## 13. Reports

- **Animal health card (PDF):** animal details, last 10 records, latest prediction, vaccination history (done reminders), consultations.
- **Herd report (PDF/CSV):** counts by species/status, alerts by type and severity, risk distribution, disease cases in range, vaccination coverage.
- **Vaccinations due (PDF/CSV):** animal tag, species, reminder title, due date, status.
- **Treatments (CSV):** date, animal tag, diagnosis, treatment, medicine, dosage, vet.
- PDFs use the Noto Sans Bengali font and respect the requesting user's `language` for headings. Use `Content-Disposition: attachment`.

---

## 14. Frontend specification

### 14.1 Routes and access

| Route | Role | Page |
| --- | --- | --- |
| `/login`, `/register`, `/forgot-password` (placeholder) | public | auth pages |
| `/` | any | redirect to role dashboard |
| `/farmer/dashboard` | farmer | dashboard |
| `/farmer/animals`, `/farmer/animals/new`, `/farmer/animals/:id`, `/farmer/animals/:id/edit` | farmer | registry |
| `/farmer/animals/:id/records/new` | farmer | health record form |
| `/farmer/import` | farmer | CSV import |
| `/farmer/alerts`, `/farmer/reminders`, `/farmer/reports` | farmer | |
| `/farmer/farms`, `/farmer/farms/:id/vets` | farmer | farm profile and vet access |
| `/vet/queue`, `/vet/cases/:animalId`, `/vet/consultations/:id`, `/vet/farms`, `/vet/invitations` | vet | |
| `/admin/users`, `/admin/vets`, `/admin/thresholds`, `/admin/schedules`, `/admin/lookups`, `/admin/audit`, `/admin/model` | admin | |
| `/profile` | any | profile and language |

Use a `ProtectedRoute` component that checks the token and the allowed roles. Unapproved vets see a "waiting for admin approval" page.

### 14.2 Layout
- Top bar: app name, language switch (EN | বাংলা), notification bell with open alert count (poll `/alerts/summary` every 60 s), user menu.
- Left sidebar on desktop, bottom tab bar or hamburger menu on mobile.
- Tailwind. Mobile-first. Minimum touch target 44 px. Good colour contrast.
- Severity colours: low = green, medium = amber, high = red. Always pair colour with text or icon.
- Show loading states, empty states, and error toasts for every data call.

### 14.3 Key pages

**Farmer dashboard:** summary cards (animals, open alerts, high-risk animals, vaccinations due), charts using recharts (animals by status, risk distribution, temperature trend line, disease cases over time, vaccination coverage), upcoming reminders list, latest alerts list. Farm selector if the farmer has more than one farm.

**Animal list:** table (cards on mobile) with tag, species, status badge, latest risk badge, last record date. Search box and filters for species and status. "Add animal" button.

**Animal profile:** header with details and status; tabs: Timeline, Records (with temperature/weight line chart), Predictions, Reminders, Consultations. Buttons: Add health record, Generate reminders, Archive, Edit.

**Health record form:** fields for temperature, weight, feed intake, milk yield, date/time; symptom checklist as large toggle chips (with Bangla labels when language is Bangla); notes. On submit show a **result panel**: risk badge, top 3 diseases with probability bars, top factors, the disclaimer, and any alerts created.

**CSV import:** file picker, link to download the sample CSV, upload, then show the import report with a table of errors (row, field, message) and a button to download the error list as CSV.

**Alerts page:** tabs Open / Acknowledged / All; filters by severity; each alert card shows severity, animal link, message, time, and buttons Acknowledge, Snooze (1h, 6h, 24h), Resolve.

**Reminders page:** upcoming and overdue lists; mark done; add reminder.

**Vet queue:** table ordered by severity, with animal tag, farm, species, latest risk, last record. Opens case page showing history, latest prediction, a **Confirm / Reject prediction** control with an optional actual disease, the consultation form (diagnosis, treatment, medicine, dosage, follow-up date), and the comment thread.

**Admin pages:** users table with approve/suspend; thresholds editable table; schedules CRUD; lookups CRUD; audit log table; model page showing `metrics.json` (accuracy, macro F1, confusion matrix as a table, "trained on synthetic data" notice).

### 14.4 Internationalization
- `react-i18next`, files `src/i18n/en.json` and `src/i18n/bn.json` with identical keys, grouped by page (`common`, `auth`, `animals`, `records`, `alerts`, `dashboard`, `vet`, `admin`, `reports`).
- Language comes from the logged-in user's `language`; the switch updates it via `PATCH /auth/me` and local storage.
- Format dates and numbers with locale (`bn-BD` for Bangla; optionally show Bangla digits).
- Server-provided names (symptoms, diseases, alert messages) use `name_bn`/`message_bn` when language is `bn`.
- Use a Bangla-capable font in Tailwind config (Noto Sans Bengali, loaded from a local file or Google Fonts).

### 14.5 Required disclaimer text
- en: `AI risk estimate to support a veterinarian. It is not a diagnosis. Consult a qualified veterinarian.`
- bn: `এটি পশুচিকিৎসককে সহায়তার জন্য এআই-ভিত্তিক ঝুঁকির অনুমান। এটি রোগনির্ণয় নয়। অনুগ্রহ করে যোগ্য পশুচিকিৎসকের পরামর্শ নিন।`

### 14.6 API client
One axios instance with base URL `/api/v1`, request interceptor adds the token, response interceptor logs out on `401` and shows a toast on other errors. One module per resource under `src/api/`.

---

## 15. Seed data (`backend/scripts/seed.py`)

Idempotent (safe to run twice). Creates:
- Symptoms and diseases from Section 6; thresholds from 9.2.
- Vaccine schedule templates (**placeholders, must be verified with a veterinarian**): FMD vaccination (cattle, goat, sheep) every 180 days; LSD vaccination (cattle) every 365 days; PPR vaccination (goat, sheep) every 365 days; Deworming (all) every 90 days; General checkup (all) every 30 days.
- Users (password `Password123!` for all, development only):
  - admin: `admin@demo.com`
  - farmer: `farmer@demo.com` (farm "Demo Farm", district Dhaka)
  - vet: `vet@demo.com` (approved, with approved access to Demo Farm)
- 12 animals: 6 cattle (tags `C-001`…`C-006`), 4 goats (`G-001`…`G-004`), 2 sheep (`S-001`, `S-002`).
- About 30 days of daily health records for each animal (using the record pipeline or a bulk insert plus predictions), with 3 animals showing a developing illness (rising temperature, falling feed intake, relevant symptoms) so alerts, predictions, and charts have real content.
- A few reminders (some due soon, one overdue) and one consultation.

---

## 16. Testing requirements

**Backend (pytest), minimum:**
- Auth: register, login, wrong password, unapproved vet blocked, role checks (farmer cannot call admin endpoints → 403).
- Access control: farmer A cannot read farmer B's animals (404); vet without approval cannot read a farm.
- Animals CRUD and unique tag per farm.
- Record validation (out-of-range values → 422; empty record → 422).
- Rule engine: fever alert thresholds, weight loss, appetite drop, de-duplication within 24 h.
- Risk level function and safety net with fixed inputs.
- Prediction service with a tiny trained model fixture; species filter sets impossible diseases to 0.
- CSV import: valid file, unknown tag, bad number, report counts.
- Reminder logic: overdue marking, next reminder after completion.
- Dashboard summary returns expected keys.

**ML:** a test that `train.py` produces `model.joblib` and `metrics.json`, and macro F1 on the synthetic test set is above 0.7 (this checks the pipeline, not clinical accuracy).

**Frontend:** at least smoke tests (Vitest + React Testing Library) for login form, protected route redirect, and the symptom chips component. Manual checklist in `README.md` for each role.

Provide `README.md` instructions to run everything:
```
# backend
python -m venv venv && venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
alembic upgrade head
python -m app.ml.train
python scripts/seed.py
uvicorn app.main:app --reload

# frontend
cd frontend && npm install && npm run dev
```

---

## 17. Build phases and acceptance criteria

**Phase 0 — Project setup**
- Create the structure in Section 3, install dependencies, config loading, database session, Alembic initialized, health endpoint, frontend scaffold with Tailwind, i18n, router.
- Accept when: `GET /health` returns ok; frontend runs and shows a language switch.

**Phase 1 — Auth and users**
- Models: users. Register, login, me, change password, roles, vet approval flag, admin approve endpoint, seed admin. Frontend: login, register, ProtectedRoute, AuthContext, role redirect.
- Accept when: three demo users can log in and land on the right dashboard; unapproved vet is blocked.

**Phase 2 — Farms and animals**
- Models: farms, farm_vets, animals, symptoms, diseases. CRUD, search, filters, status, archive, vet invitation flow, access rules. Frontend: farm page, animal list, add/edit, profile shell.
- Accept when: farmer manages animals; another farmer cannot see them; vet sees them only after approval.

**Phase 3 — Health records and CSV import**
- Models: health_records, record_symptoms. Validation, derived values, form, list, chart, CSV import with report, sample CSV. (Prediction and alerts not yet.)
- Accept when: records save with symptoms; CSV import reports errors by row.

**Phase 4 — AI prediction**
- ml/ package, synthetic data, training, metrics, predict service, models predictions and prediction_feedback, risk level, safety net, species filter, explanation, result panel in the record form, admin model page.
- Accept when: `python -m app.ml.train` succeeds with macro F1 above 0.7; saving a record returns a prediction with confidence and factors; high-risk inputs give `high`.

**Phase 5 — Alerts, reminders, scheduler, email**
- Models: alerts, thresholds, vaccine_schedules, reminders, notification_log. Rule engine, de-duplication, bilingual messages, email service (log mode), scheduler jobs, manual job trigger, alerts and reminders pages, bell badge.
- Accept when: an abnormal reading creates an alert and an email log row; running `reminders_daily` creates reminder alerts; acknowledge and snooze work.

**Phase 6 — Veterinarian module**
- Models: consultations, consultation_comments. Queue, case page, prediction feedback, treatment form, follow-up reminder, comments.
- Accept when: a vet records a diagnosis and treatment; farmer sees it on the animal profile; feedback is saved.

**Phase 7 — Dashboard and reports**
- Dashboard summary endpoint and charts; PDF and CSV reports with Bangla text rendering.
- Accept when: dashboard shows seeded data; the PDF health card opens with Bangla headings correctly.

**Phase 8 — Admin and polish**
- Thresholds, schedules, lookups, audit log, user management; mobile layout pass; empty/loading/error states; accessibility pass; complete Bangla translations.
- Accept when: changing a threshold changes alert behavior; every page works at 375 px width.

**Phase 9 — Tests, seed, docs**
- Seed script complete, test suite passing, README with run steps and demo script, `ASSUMPTIONS.md` finalized.
- Accept when: a fresh clone can run end to end using the README.

---

## 18. Out of scope (do not build)

- Physical sensors, collars, or hardware drivers (only the API-key endpoint in 8.11)
- Native mobile apps
- Marketplace, payments, or billing
- Image or video-based diagnosis
- SMS or push notifications
- Automatic model retraining
- Social login
- Anything that presents the AI output as a final diagnosis

---

## 19. Definition of done

- All phases meet their acceptance criteria.
- Backend tests pass; ML test passes.
- No secrets committed; `.env.example` provided.
- Every screen works in English and Bangla and on a phone-sized screen.
- The AI disclaimer appears wherever predictions are shown.
- README explains setup, demo accounts, and a 5-minute demo script covering: log in as farmer → add health record → see prediction and alert → log in as vet → review and record treatment → view dashboard and download a report.
