# Parking Lot API

The backend of [parking_management](https://github.com/paulmrg-461/parking_management): a FastAPI
service for parking operators. Operators check vehicles in and out; the API prices each stay from
the vehicle category's tariffs, tracks monthly passes and reports revenue and occupancy.

Business rules are specified in `openspec/specs/` (billing in `openspec/specs/billing/spec.md`).
Calendar days, night windows and report days are evaluated in `BUSINESS_TIMEZONE`
(default `America/Bogota`).

```sh
pip install -r requirements.txt
pytest
ENVIRONMENT=development DATABASE_URL=sqlite+aiosqlite:///./parking.db uvicorn app.main:app
```

Set `LOG_FORMAT=json` (and optionally `LOG_FILE`) for one JSON log record per line.
