#!/usr/bin/env python3

import json
import os
import sqlite3
import urllib.request
from datetime import datetime
from pathlib import Path

DB_PATH = Path("/config/leapmotor/leapmotor_trip.db")
OUT_PATH = Path("/config/www/leapmotor/charge_efficiency_summary.json")

BATTERY_CAPACITY_KWH = float(os.environ.get("BATTERY_CAPACITY_KWH", "67.1"))
SOC_RECHARGE_JUMP_THRESHOLD = 5.0

ENV_STATE_MAP = {
    "input_boolean.leapmotor_ricarica_attiva": "LEAP_RICARICA_ATTIVA",
    "input_datetime.leapmotor_ricarica_start": "LEAP_RICARICA_START",
    "input_datetime.leapmotor_ricarica_end": "LEAP_RICARICA_END",
    "input_number.leapmotor_ricarica_soc_start": "LEAP_RICARICA_SOC_START",
    "input_number.leapmotor_ricarica_soc_end": "LEAP_RICARICA_SOC_END",
    "sensor.leapmotor_precise_battery": "LEAP_SOC_LIVE",
    "binary_sensor.leapmotor_cavo_ricarica_collegato": "LEAP_CAVO",
    "binary_sensor.leapmotor_charging": "LEAP_CHARGING",
    "sensor.leapmotor_charging_connection": "LEAP_CHARGING_CONNECTION",
    "sensor.leapmotor_wallbox_power_filtered": "LEAP_WALLBOX_POWER",
    "sensor.leapmotor_charging_power_filtered": "LEAP_BATTERY_POWER",
}



def safe_float(value, default=0.0):
    try:
        if value in (None, "", "unknown", "unavailable", "none"):
            return default
        return float(value)
    except Exception:
        return default


def parse_dt(value):
    if not value:
        return None
    value = str(value).replace("+00:00", "")[:19]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt)
        except Exception:
            pass
    return None


def get_supervisor_token():
    token = os.environ.get("SUPERVISOR_TOKEN")
    if token:
        return token.strip()

    for token_path in (
        "/run/s6/container_environment/SUPERVISOR_TOKEN",
        "/var/run/s6/container_environment/SUPERVISOR_TOKEN",
    ):
        try:
            value = Path(token_path).read_text().strip()
            if value:
                return value
        except Exception:
            pass

    return None


def get_ha_state(entity_id):
    token = get_supervisor_token()
    if not token:
        return {"state": "unknown", "attributes": {}}

    url = f"http://supervisor/core/api/states/{entity_id}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return {"state": "unknown", "attributes": {}}


def state(entity_id):
    env_name = ENV_STATE_MAP.get(entity_id)
    if env_name:
        env_value = os.environ.get(env_name)
        if env_value not in (None, ""):
            return env_value

    return get_ha_state(entity_id).get("state", "unknown")


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


def row_to_trip(r):
    return {
        "id": r["id"],
        "start": r["start"],
        "end": r["end"],
        "duration": r["durata"] if "durata" in r.keys() else "",
        "duration_minutes": duration_to_minutes(r["durata"] if "durata" in r.keys() else ""),
        "km": safe_float(r["km"]),
        "kwh": safe_float(r["kwh"]),
        "cons": safe_float(r["cons"]),
        "soc_start": safe_float(r["soc_start"]),
        "soc_end": safe_float(r["soc_end"]),
        "vel_media": safe_float(r["vel_media"]),
        "temperatura": safe_float(r["temperatura"]),
    }


def main():
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    now = datetime.now()

    ricarica_attiva = state("input_boolean.leapmotor_ricarica_attiva")
    start_charge = state("input_datetime.leapmotor_ricarica_start")
    end_charge = state("input_datetime.leapmotor_ricarica_end")

    soc_start = safe_float(state("input_number.leapmotor_ricarica_soc_start"))
    soc_end_saved = safe_float(state("input_number.leapmotor_ricarica_soc_end"))
    soc_live = safe_float(state("sensor.leapmotor_precise_battery"))

    cable = state("binary_sensor.leapmotor_cavo_ricarica_collegato")
    charging = state("binary_sensor.leapmotor_charging")
    charging_connection = state("sensor.leapmotor_charging_connection")

    wallbox_power = safe_float(state("sensor.leapmotor_wallbox_power_filtered"))
    battery_power = safe_float(state("sensor.leapmotor_charging_power_filtered"))

    charge_start_dt = parse_dt(start_charge)
    charge_end_dt = parse_dt(end_charge)

    if ricarica_attiva == "on":
        current_soc_end = soc_live
        session_status = "in_progress"
        effective_end_dt = now
    else:
        current_soc_end = soc_end_saved
        session_status = "completed" if soc_end_saved > 0 else "none"
        effective_end_dt = charge_end_dt or now

    soc_added = max(current_soc_end - soc_start, 0) if soc_start > 0 else 0
    estimated_kwh_added = round((soc_added / 100) * BATTERY_CAPACITY_KWH, 2)

    duration_minutes = 0
    if charge_start_dt:
        duration_minutes = max(int((effective_end_dt - charge_start_dt).total_seconds() // 60), 0)

    duration_label = f"{duration_minutes // 60:02d}:{duration_minutes % 60:02d}"

    avg_charge_power = 0
    if duration_minutes > 0 and estimated_kwh_added > 0:
        avg_charge_power = round(estimated_kwh_added / (duration_minutes / 60), 2)

    selected_trips = []
    all_trips_before_charge = []
    detected_previous_charge = None

    if DB_PATH.exists() and charge_start_dt:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT *
            FROM trips
            WHERE end IS NOT NULL
              AND end != ''
              AND datetime(end) <= datetime(?)
            ORDER BY datetime(end) ASC
            """,
            (start_charge,),
        ).fetchall()

        conn.close()

        # Deduplica semplice: evita trip con stesso start/end/km/kWh.
        seen = set()
        trips = []
        for r in rows:
            key = (r["start"], r["end"], safe_float(r["km"]), safe_float(r["kwh"]))
            if key in seen:
                continue
            seen.add(key)

            trip = row_to_trip(r)
            end_dt = parse_dt(trip["end"])
            if not end_dt:
                continue

            # Limite ragionevole: non più di 60 giorni indietro.
            if (charge_start_dt - end_dt).days > 60:
                continue

            trips.append(trip)

        all_trips_before_charge = trips

        # Cerca ultimo salto SOC positivo tra due trip consecutivi.
        start_index = 0
        for i in range(1, len(trips)):
            prev_soc_end = safe_float(trips[i - 1]["soc_end"])
            curr_soc_start = safe_float(trips[i]["soc_start"])

            if prev_soc_end > 0 and curr_soc_start > 0:
                jump = curr_soc_start - prev_soc_end
                if jump >= SOC_RECHARGE_JUMP_THRESHOLD:
                    start_index = i
                    detected_previous_charge = {
                        "after_trip_id": trips[i - 1]["id"],
                        "before_trip_id": trips[i]["id"],
                        "previous_soc_end": round(prev_soc_end, 1),
                        "next_soc_start": round(curr_soc_start, 1),
                        "soc_jump": round(jump, 1),
                        "estimated_at": trips[i]["start"],
                    }

        selected_trips = trips[start_index:]

    total_km = round(sum(t["km"] for t in selected_trips), 2)
    total_kwh = round(sum(t["kwh"] for t in selected_trips), 2)
    total_duration = sum(t["duration_minutes"] for t in selected_trips)

    cons = round((total_kwh / total_km) * 100, 2) if total_km > 0 else 0
    km_per_kwh = round(total_km / total_kwh, 2) if total_kwh > 0 else 0
    avg_speed = round(total_km / (total_duration / 60), 1) if total_duration > 0 else 0

    # Protezione: se lo script viene lanciato da HA senza stati validi,
    # non sovrascrive il riepilogo valido precedente con un JSON vuoto.
    invalid_live_context = (
        ricarica_attiva == "unknown"
        and cable == "unknown"
        and charging == "unknown"
        and start_charge == "unknown"
        and soc_start == 0
        and soc_live == 0
    )

    if invalid_live_context and OUT_PATH.exists():
        print("WARN: stati HA non disponibili; mantengo il JSON precedente.")
        return

    output = {
        "generated_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "battery_capacity_kwh": BATTERY_CAPACITY_KWH,
        "current_charge_session": {
            "status": session_status,
            "ricarica_attiva": ricarica_attiva,
            "cable": cable,
            "charging": charging,
            "charging_connection": charging_connection,
            "start": start_charge,
            "end": end_charge,
            "duration_minutes": duration_minutes,
            "duration_label": duration_label,
            "soc_start": round(soc_start, 1),
            "soc_current_or_end": round(current_soc_end, 1),
            "soc_added": round(soc_added, 1),
            "estimated_kwh_added": estimated_kwh_added,
            "avg_charge_power_kw": avg_charge_power,
            "wallbox_power_kw": wallbox_power,
            "battery_power_kw": battery_power,
        },
        "since_previous_charge": {
            "method": "detected_by_soc_jump",
            "soc_jump_threshold": SOC_RECHARGE_JUMP_THRESHOLD,
            "detected_previous_charge": detected_previous_charge,
            "from": selected_trips[0]["start"] if selected_trips else None,
            "to": start_charge if charge_start_dt else None,
            "trips": len(selected_trips),
            "km": total_km,
            "kwh": total_kwh,
            "duration_minutes": total_duration,
            "duration_label": f"{total_duration // 60:02d}:{total_duration % 60:02d}",
            "cons_kwh_100km": cons,
            "km_per_kwh": km_per_kwh,
            "avg_speed_kmh": avg_speed,
            "soc_start": round(selected_trips[0]["soc_start"], 1) if selected_trips else 0,
            "soc_end": round(selected_trips[-1]["soc_end"], 1) if selected_trips else 0,
            "soc_used": round(
                selected_trips[0]["soc_start"] - selected_trips[-1]["soc_end"], 1
            ) if selected_trips else 0,
        },
        "recent_trips_used": selected_trips[-30:],
        "all_trips_before_charge_count": len(all_trips_before_charge),
    }

    OUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"OK: scritto {OUT_PATH}")


if __name__ == "__main__":
    main()
