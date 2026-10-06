"""Replays one business day of a parking lot against the backend and keeps its JSON log.

The app runs in-process on a throwaway SQLite database with a simulated clock, so a day
of check-ins, check-outs, list refreshes and reports takes seconds. Log timestamps follow
the simulated clock. Output: ./logs/parking-lot.log (a previous log moves to ./logs/archive/).

    python generate_logs.py [--day 2026-10-05] [--seed 7]

Run from any directory with the backend's requirements installed (run.sh does both).
"""

import argparse
import asyncio
import logging
import os
import random
import secrets
import shutil
import sys
import sysconfig
import tempfile
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
UPSTREAM = HERE.parent / "upstream"
ZONE = ZoneInfo("America/Bogota")

parser = argparse.ArgumentParser()
parser.add_argument("--day", default="2026-10-05", help="the business day to replay (local date)")
parser.add_argument("--seed", type=int, default=7)
args = parser.parse_args()
DAY = date.fromisoformat(args.day)
rng = random.Random(args.seed)

work = Path(tempfile.mkdtemp(prefix="parking-lot-"))
raw_log = work / "app.log"
os.environ.update({
    "ENVIRONMENT": "production",
    "SECRET_KEY": secrets.token_urlsafe(48),
    "DATABASE_URL": f"sqlite+aiosqlite:///{work / 'parking.db'}",
    "EVIDENCE_STORAGE_PATH": str(work / "evidence"),
    "BUSINESS_TIMEZONE": "America/Bogota",
    "LOG_FORMAT": "json",
    "LOG_FILE": str(raw_log),
})
sys.path.insert(0, str(UPSTREAM))

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

import app.infrastructure.models  # noqa: E402,F401  (registers the tables)
from app.core.security import hash_password  # noqa: E402
from app.domain.user import User, UserRole  # noqa: E402
from app.infrastructure.database import Base, async_session_factory, engine  # noqa: E402
from app.infrastructure.repositories.user_repository import SqlAlchemyUserRepository  # noqa: E402
from app.main import app  # noqa: E402
from app.presentation.deps import get_clock  # noqa: E402


class SimClock:
    def __init__(self, start: datetime):
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


clock = SimClock(datetime.combine(DAY - timedelta(days=1), time(17, 0), tzinfo=ZONE).astimezone(UTC))
app.dependency_overrides[get_clock] = lambda: clock
_factory = logging.getLogRecordFactory()


def _sim_record(*a, **kw):
    record = _factory(*a, **kw)
    record.created = clock.now.timestamp()
    return record


logging.setLogRecordFactory(_sim_record)


@event.listens_for(engine.sync_engine, "connect")
def _on_connect(dbapi_connection, _record):
    dbapi_connection.isolation_level = None


@event.listens_for(engine.sync_engine, "begin")
def _on_begin(connection):
    connection.exec_driver_sql("BEGIN")


def local(day: date, hour: float) -> datetime:
    return (datetime.combine(day, time(0, 0), tzinfo=ZONE) + timedelta(hours=hour)).astimezone(UTC)


def arrivals_per_hour(hour: int) -> float:
    return {5: 5, 6: 9, 7: 14, 8: 12, 9: 8, 17: 10, 18: 9, 19: 6}.get(
        hour, 7 if 10 <= hour < 17 else 4 if 20 <= hour < 23 else 1)


def departure(arrived: datetime) -> datetime:
    local_arrival = arrived.astimezone(ZONE)
    hour, roll = local_arrival.hour, rng.random()
    if 5 <= hour < 9:  # commuters; some stay late, leaving before midnight
        if roll < 0.25:
            return local(local_arrival.date(), rng.uniform(22.1, 23.8))
        return arrived + timedelta(hours=rng.uniform(7.5, 9.5) if roll < 0.8 else rng.uniform(9.5, 11.5))
    if 17 <= hour < 22 and roll < 0.15:  # residents leaving next morning
        return local(local_arrival.date() + timedelta(days=1), rng.uniform(6.5, 9.5))
    return arrived + timedelta(hours=rng.uniform(0.4, 4))


async def main() -> None:
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with async_session_factory() as session:
        await SqlAlchemyUserRepository(session).create(
            User(id=None, username="admin", display_name="Admin", role=UserRole.ADMIN, pin_hash=hash_password("2580")))
        await session.commit()

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://parking.internal") as http:
            async def call(method: str, url: str, headers: dict, **kw):
                clock.advance(seconds=rng.uniform(0.2, 9))
                return await http.request(method, url, headers=headers, **kw)

            async def login(username: str, pin: str) -> dict:
                response = await call("POST", "/api/auth/login", {}, json={"username": username, "pin": pin})
                return {"Authorization": f"Bearer {response.json()['access_token']}"}

            admin = await login("admin", "2580")
            for name in ("lucia", "andres"):
                await call("POST", "/api/users", admin, json={"username": name, "display_name": name.title(),
                                                              "role": "operator", "pin": "4711"})
            operators = [await login("lucia", "4711"), await login("andres", "4711")]
            categories = {}
            for name, hourly, daily, nightly in (("Car", 3000, 25000, 2000), ("Motorcycle", 1500, 12000, 1000)):
                category = (await call("POST", "/api/categories", admin, json={"name": name})).json()
                categories[name] = category["id"]
                for kind, amount in (("hourly", hourly), ("daily", daily)):
                    await call("POST", "/api/tariffs", admin, json={"category_id": category["id"], "type": kind, "amount": amount})
                await call("POST", "/api/tariffs", admin, json={"category_id": category["id"], "type": "nightly",
                                                                "amount": nightly, "start_time": "22:00", "end_time": "06:00"})

            letters = "ABCDEFGHJKLMNPRSTUVWXYZ"
            plates = [f"{''.join(rng.choice(letters) for _ in range(3))}{rng.randint(100, 999)}" for _ in range(260)]
            category_of = {p: ("Motorcycle" if rng.random() < 0.25 else "Car") for p in plates}
            parked: dict[str, tuple[int, datetime]] = {}   # plate -> (session id, planned exit)
            failed: dict[int, int] = {}                    # session id -> failed check-out attempts
            passes_done = False
            end = local(DAY + timedelta(days=1), 0.5)
            next_poll = [clock.now + timedelta(minutes=10), clock.now + timedelta(minutes=25)]
            next_report = local(DAY, 8)
            stats: dict[str, int] = {}

            def count(key: str) -> None:
                stats[key] = stats.get(key, 0) + 1

            while clock.now < end:
                hour = clock.now.astimezone(ZONE).hour
                clock.advance(minutes=rng.expovariate(arrivals_per_hour(hour) / 60))
                operator = rng.choice(operators)

                # Arrivals
                free = [p for p in plates if p not in parked]
                plate = rng.choice(free)
                response = await call("POST", "/api/check-ins", operator,
                                      data={"plate": plate, "category_id": str(categories[category_of[plate]])})
                count(f"check-in {response.status_code}")
                if response.status_code == 201:
                    parked[plate] = (response.json()["id"], departure(clock.now))

                if not passes_done and clock.now >= local(DAY, 6):
                    # A few regulars hold monthly passes.
                    vehicles = (await call("GET", "/api/vehicles", admin)).json()
                    for vehicle in vehicles[:6]:
                        await call("POST", "/api/monthly-passes", admin, json={
                            "vehicle_id": vehicle["id"], "start_date": str(DAY - timedelta(days=12)),
                            "end_date": str(DAY + timedelta(days=18)), "amount": 180000})
                    passes_done = True

                # Departures due by now (failed check-outs are retried a little later, at most twice)
                for plate, (session_id, leaves) in sorted(parked.items(), key=lambda item: item[1][1]):
                    if leaves > clock.now:
                        continue
                    response = await call("POST", f"/api/check-outs/{session_id}", rng.choice(operators))
                    count(f"check-out {response.status_code}")
                    if response.status_code == 200:
                        del parked[plate]
                    elif failed.get(session_id, 0) < 2:
                        failed[session_id] = failed.get(session_id, 0) + 1
                        parked[plate] = (session_id, clock.now + timedelta(minutes=rng.uniform(8, 25)))
                    else:
                        del parked[plate]  # the driver paid in cash and left; the session stays open

                # Each operator's tablet refreshes the open-sessions list now and then
                for i, op in enumerate(operators):
                    if clock.now >= next_poll[i]:
                        response = await call("GET", "/api/check-ins?limit=50", op)
                        count(f"list {response.status_code}")
                        next_poll[i] = clock.now + timedelta(minutes=rng.uniform(20, 45))

                if clock.now >= next_report:
                    today = clock.now.astimezone(ZONE).date()
                    await call("GET", f"/api/reports/revenue?start_date={today}&end_date={today}", admin)
                    await call("GET", "/api/reports/occupancy", admin)
                    next_report = clock.now + timedelta(hours=rng.uniform(3, 5))

    await engine.dispose()
    logging.shutdown()

    text = raw_log.read_text()
    # Show code paths as they appear in the production image (WORKDIR /app).
    for real, shown in ((str(UPSTREAM), "/app"), (sysconfig.get_paths()["purelib"], "/usr/local/lib/python3.12/site-packages"),
                        (sysconfig.get_paths()["stdlib"], "/usr/local/lib/python3.12")):
        text = text.replace(real, shown)
    logs = HERE / "logs"
    (logs / "archive").mkdir(parents=True, exist_ok=True)
    out = logs / "parking-lot.log"
    if out.exists():
        out.rename(logs / "archive" / f"parking-lot-{datetime.now(UTC):%Y%m%dT%H%M%S}.log")
    out.write_text(text)
    shutil.rmtree(work, ignore_errors=True)

    import json
    errors: dict[str, int] = {}
    for line in text.splitlines():
        record = json.loads(line)
        if record["level"] == "error":
            errors[record["message"]] = errors.get(record["message"], 0) + 1
    print("[generate_logs] requests", dict(sorted(stats.items())))
    print("[generate_logs] error records", errors)
    print(f"[generate_logs] wrote {out} ({len(text.splitlines())} records)")


asyncio.run(main())
