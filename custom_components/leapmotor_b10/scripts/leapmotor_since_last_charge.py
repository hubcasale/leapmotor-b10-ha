#!/usr/bin/env python3

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path


TRIP_DB = "/config/leapmotor/leapmotor_trip.db"
OUTPUT_FILE = Path("/config/www/leapmotor/since_last_charge.json")

# Soglia per considerare una ricarica reale.
# Evita falsi positivi da micro-variazioni SOC.
SOC_CHARGE_THRESHOLD = 0.5


def safe_float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def weighted_consumption(kwh, km):
    if km <= 0:
        return 0
    return round((kwh / km) * 100, 2)


def load_trips():
    if not os.path.exists(TRIP_DB):
        raise FileNotFoundError(f"DB viaggi non trovato: {TRIP_DB}")

    conn = sqlite3.connect(TRIP_DB)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
          id,
          start,
          end,
          durata,
          km,
          kwh,
          cons,
          soc_start,
          soc_end,
          vel_media,
          temperatura,
          note
        FROM trips
        WHERE start IS NOT NULL
          AND start != ''
          AND end IS NOT NULL
          AND end != ''
        ORDER BY start ASC
        """
    ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def find_last_charge_start_index(trips):
    """
    Cerca l'ultima ricarica guardando il salto SOC tra:
    viaggio precedente soc_end -> viaggio successivo soc_start.

    Se soc_start del viaggio successivo è maggiore di soc_end del precedente
    oltre soglia, assumiamo che ci sia stata una ricarica tra i due.
    """
    last_index = 0
    charge_detected = False
    charge_info = None

    for i in range(1, len(trips)):
        prev_trip = trips[i - 1]
        curr_trip = trips[i]

        prev_soc_end = safe_float(prev_trip.get("soc_end"))
        curr_soc_start = safe_float(curr_trip.get("soc_start"))

        if curr_soc_start > prev_soc_end + SOC_CHARGE_THRESHOLD:
            last_index = i
            charge_detected = True
            charge_info = {
                "previous_trip_id": prev_trip.get("id"),
                "next_trip_id": curr_trip.get("id"),
                "previous_soc_end": round(prev_soc_end, 1),
                "next_soc_start": round(curr_soc_start, 1),
                "soc_increase": round(curr_soc_start - prev_soc_end, 1),
                "detected_between": {
                    "previous_trip_end": prev_trip.get("end"),
                    "next_trip_start": curr_trip.get("start"),
                },
            }

    return last_index, charge_detected, charge_info


def build_summary(trips):
    if not trips:
        return {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "available": False,
            "reason": "Nessun viaggio disponibile",
            "trips": 0,
            "km": 0,
            "kwh": 0,
            "cons": 0,
        }

    start_index, charge_detected, charge_info = find_last_charge_start_index(trips)
    selected = trips[start_index:]

    total_km = round(sum(safe_float(t.get("km")) for t in selected), 2)
    total_kwh = round(sum(safe_float(t.get("kwh")) for t in selected), 2)

    first_trip = selected[0]
    last_trip = selected[-1]

    soc_start = safe_float(first_trip.get("soc_start"))
    soc_end = safe_float(last_trip.get("soc_end"))

    result = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "available": True,
        "charge_detected": charge_detected,
        "charge_info": charge_info,
        "trips": len(selected),
        "km": total_km,
        "kwh": total_kwh,
        "cons": weighted_consumption(total_kwh, total_km),
        "soc_start": round(soc_start, 1),
        "soc_end": round(soc_end, 1),
        "soc_delta": round(soc_start - soc_end, 1),
        "first_trip_id": first_trip.get("id"),
        "last_trip_id": last_trip.get("id"),
        "first_trip_start": first_trip.get("start"),
        "last_trip_end": last_trip.get("end"),
        "trip_ids": [t.get("id") for t in selected],
    }

    return result


def main():
    trips = load_trips()
    summary = build_summary(trips)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"File generato: {OUTPUT_FILE}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
