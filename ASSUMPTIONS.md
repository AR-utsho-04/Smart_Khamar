# Assumptions and differences from SPEC.md

## Technical choices
- **Database tables** are created automatically on startup (`Base.metadata.create_all`). Alembic migrations were not added (not needed for a single-developer course project).
- **SQLite** is the default database (`DATABASE_URL` in `.env`). The code also works with PostgreSQL by changing that one line.
- **APScheduler** runs background jobs inside the backend. No Redis or Celery needed.
- **Frontend routes are role-neutral** (`/animals`, `/alerts`, `/reminders`, `/reports`) instead of `/farmer/...`. The menu and the API still enforce roles.
- **Passwords** are limited to 8-64 characters (bcrypt limit).
- **Prediction time** equals the time of the health record, so charts follow the measurement date.
- Animal status moves up automatically (healthy -> under observation -> sick). Moving back to healthy or recovered is a manual action by the farmer or vet.

## Built (all Must features, plus these Should/Could items)
- Search and filters, animal status, valid-range checks, explanation of AI results, vet feedback on predictions
- Rule-based safety net, severity levels, acknowledge / snooze / resolve, escalation of unacknowledged high alerts
- Admin-editable thresholds, vaccination schedules, symptom and disease names, audit log, manual job runner
- Comment thread between farmer and vet, follow-up reminders from consultations
- Sensor-ready endpoint `POST /api/v1/readings` (API key), export script for vet-confirmed cases

## IoT feature (added after SPEC.md)
- Devices send readings over **HTTP** with a per-device key. MQTT/LoRaWAN are not implemented.
- The sensor AI (Isolation Forest + rules + persistence) is trained on **simulated** normal behaviour; species baselines are placeholders. Low activity at night cannot be told apart from sleep.
- The ESP32 firmware in `iot/` is an example and was **not tested on real hardware**.
- `IOT_DEMO_SIMULATOR=true` runs a built-in thread that keeps 3 demo collars sending data (used by the online demo).
- No rate limiting on the telemetry endpoint; sensor trends are not yet inputs to the disease-risk model.

## Not built (listed as Should/Could in SPEC.md)
- Password reset by email, email OTP (2FA), SMS alerts
- Bulk "quick entry" for many animals on one screen, QR codes, installable PWA / offline mode
- Prescription PDF, medicine withdrawal notes, database backup button, photo upload (the `photo_url` field exists)
- Date-range filter on the dashboard screen (the API supports `from` and `to`)
- Automatic model retraining

## Honest notes
- **AI data:** the model is trained on synthetic data made from simplified rules (`backend/app/ml/generate_data.py`). It proves the pipeline works. It is **not** real-world accuracy. Replace the generator with real veterinary data to improve it.
- **Medical values** (temperature limits, vaccination intervals, disease and symptom lists) are approximate placeholders. Confirm them with a veterinarian.
- **PDF reports are in English.** The PDF library cannot shape Bangla conjunct letters correctly. The website itself is fully Bangla/English.
- **Email** is only logged (database table `notification_log` and the backend console) until you fill the `SMTP_*` values in `.env`.
- Bangla translations should be reviewed by a native speaker.
