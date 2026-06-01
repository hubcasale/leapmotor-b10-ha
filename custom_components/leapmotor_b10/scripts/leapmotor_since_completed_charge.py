#!/usr/bin/env python3

import json
import os
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path

DB_PATH = Path("/config/leapmotor/leapmotor_trip.db")
OUT_PATH = Path("/config/www/leapmotor/since_completed_charge.json")

HA_URL = "http://supervisor/core/api"
TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")


def parse_dt(value):
    if not value or value in ["unknown", "unavailable", "none", "None"]:
        return None
    value = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=None)
        except Exception:
            pass
    try:
        return datetime.fromisoformat(value).replace(tzinfo=None)
    except Exception:
        return None


def safe_float(value):
    try:
        return float(value)
    except Exception:
        return 0.0


def duration_to_minutes(value):
    if not value:
        return 0
    try:
        parts = str(value).split(":")
        if len(parts) == 2:
            h, m = parts
            return int(h) * 60 + int(m)
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 60 + int(m) + (1 if int(s) >= 30 else 0)
    except Exception:
        return 0
    return 0


def minutes_to_label(minutes):
    minutes = int(minutes or 0)
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def weighted_consumption(kwh, km):
    if km <= 0:
        return 0
    return round((kwh / km) * 100, 2)


def get_ha_state(entity_id):
    if not TOKEN:
        return None

    req = urllib.request.Request(
        f"{HA_URL}/states/{entity_id}",
        headers={"Authorization": f"Bearer {TOKEN}"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data.get("state")
    except Exception:
        return None


def fallback_charge_end_from_json():
    path = Path("/config/www/leapmotor/charge_efficiency_summary.json")
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        session = data.get("current_charge_session") or {}
        return session.get("end")
    except Exception:
        return None


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    charge_end_raw = get_ha_state("input_datetime.leapmotor_ricarica_end")
    if not charge_end_raw:
        charge_end_raw = fallback_charge_end_from_json()

    charge_end = parse_dt(charge_end_raw)

    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "from": charge_end.strftime("%Y-%m-%d %H:%M:%S") if charge_end else None,
        "to": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "trips": 0,
            "km": 0,
            "kwh": 0,
            "cons_kwh_100km": 0,
            "km_per_kwh": 0,
            "duration_minutes": 0,
            "duration_label": "00:00",
            "avg_speed_kmh": 0,
            "soc_start": 0,
            "soc_end": 0,
            "soc_used": 0,
        },
        "trips": [],
        "latest_trip": None,
    }

    if not charge_end or not DB_PATH.exists():
        OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"OK: scritto {OUT_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT *
        FROM trips
        WHERE start > ?
        ORDER BY start ASC
        """,
        (charge_end.strftime("%Y-%m-%d %H:%M:%S"),)
    ).fetchall()

    conn.close()

    trips = []
    total_km = 0.0
    total_kwh = 0.0
    total_minutes = 0

    for r in rows:
        km = safe_float(r["km"])
        kwh = safe_float(r["kwh"])
        minutes = duration_to_minutes(r["durata"])

        total_km += km
        total_kwh += kwh
        total_minutes += minutes

        trip = {
            "id": r["id"],
            "start": r["start"],
            "end": r["end"],
            "start_time": str(r["start"])[11:16] if r["start"] else "",
            "end_time": str(r["end"])[11:16] if r["end"] else "",
            "duration": r["durata"],
            "duration_minutes": minutes,
            "km": round(km, 2),
            "kwh": round(kwh, 2),
            "cons": safe_float(r["cons"]),
            "soc_start": safe_float(r["soc_start"]),
            "soc_end": safe_float(r["soc_end"]),
            "vel_media": safe_float(r["vel_media"]),
            "temperatura": safe_float(r["temperatura"]),
            "note": r["note"] or "",
        }
        trips.append(trip)

    soc_start = trips[0]["soc_start"] if trips else 0
    soc_end = trips[-1]["soc_end"] if trips else 0
    soc_used = round(soc_start - soc_end, 1) if trips else 0

    km_per_kwh = round(total_km / total_kwh, 2) if total_kwh > 0 else 0
    avg_speed = round((total_km / total_minutes) * 60, 1) if total_minutes > 0 else 0

    result["summary"] = {
        "trips": len(trips),
        "km": round(total_km, 2),
        "kwh": round(total_kwh, 2),
        "cons_kwh_100km": weighted_consumption(total_kwh, total_km),
        "km_per_kwh": km_per_kwh,
        "duration_minutes": total_minutes,
        "duration_label": minutes_to_label(total_minutes),
        "avg_speed_kmh": avg_speed,
        "soc_start": round(soc_start, 1),
        "soc_end": round(soc_end, 1),
        "soc_used": soc_used,
    }

    result["trips"] = trips
    result["latest_trip"] = trips[-1] if trips else None

    OUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"OK: scritto {OUT_PATH}")


if __name__ == "__main__":
    main()
