import sqlite3
import json
from pathlib import Path
from datetime import datetime, date, timedelta
from collections import defaultdict

DB_PATH = Path("/config/leapmotor/leapmotor_trip.db")
OUTPUT_PATH = Path("/config/www/leapmotor/trip_summary.json")


def parse_dt(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")


def safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def weighted_consumption(total_kwh, total_km):
    if total_km <= 0:
        return 0.0
    return round((total_kwh / total_km) * 100, 2)


def empty_summary():
    return {
        "trips": 0,
        "km": 0.0,
        "kwh": 0.0,
        "cons": 0.0,
        "duration_minutes": 0,
    }


def add_to_summary(summary, trip):
    summary["trips"] += 1
    summary["km"] += safe_float(trip["km"])
    summary["kwh"] += safe_float(trip["kwh"])
    summary["duration_minutes"] += int(trip["duration_minutes"])
    summary["km"] = round(summary["km"], 2)
    summary["kwh"] = round(summary["kwh"], 2)
    summary["cons"] = weighted_consumption(summary["kwh"], summary["km"])


def duration_to_minutes(value):
    if not value:
        return 0

    try:
        parts = value.split(":")
        if len(parts) == 2:
            hours = int(parts[0])
            minutes = int(parts[1])
            return hours * 60 + minutes
        if len(parts) == 3:
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            return hours * 60 + minutes + (1 if seconds >= 30 else 0)
    except Exception:
        return 0

    return 0


def month_name_it(month_number):
    names = {
        1: "Gennaio",
        2: "Febbraio",
        3: "Marzo",
        4: "Aprile",
        5: "Maggio",
        6: "Giugno",
        7: "Luglio",
        8: "Agosto",
        9: "Settembre",
        10: "Ottobre",
        11: "Novembre",
        12: "Dicembre",
    }
    return names.get(month_number, str(month_number))


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    rows = conn.execute(
        """
        SELECT
            id,
            start,
            end,
            durata,
            km_start,
            km_end,
            km,
            kwh,
            cons,
            soc_start,
            soc_end,
            vel_media,
            temperatura,
            note
        FROM trips
        ORDER BY start DESC
        """
    ).fetchall()

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)

    periods = {
        "today": empty_summary(),
        "week": empty_summary(),
        "month": empty_summary(),
        "year": empty_summary(),
        "all": empty_summary(),
    }

    tree = {}

    latest_trip = None
    flat_trips = []

    for row in rows:
        start_dt = parse_dt(row["start"])
        end_dt = parse_dt(row["end"])

        if not start_dt:
            continue

        trip_date = start_dt.date()
        year_key = str(start_dt.year)
        month_key = f"{start_dt.month:02d}"
        day_key = start_dt.strftime("%Y-%m-%d")

        trip = {
            "id": row["id"],
            "start": row["start"],
            "end": row["end"],
            "date": day_key,
            "start_time": start_dt.strftime("%H:%M"),
            "end_time": end_dt.strftime("%H:%M") if end_dt else "",
            "duration": row["durata"],
            "duration_minutes": duration_to_minutes(row["durata"]),
            "km_start": safe_float(row["km_start"]),
            "km_end": safe_float(row["km_end"]),
            "km": safe_float(row["km"]),
            "kwh": safe_float(row["kwh"]),
            "cons": safe_float(row["cons"]),
            "soc_start": safe_float(row["soc_start"]),
            "soc_end": safe_float(row["soc_end"]),
            "vel_media": safe_float(row["vel_media"]),
            "temperatura": safe_float(row["temperatura"]),
            "note": row["note"] or "",
        }

        if latest_trip is None:
            latest_trip = trip

        flat_trips.append(trip)

        add_to_summary(periods["all"], trip)

        if trip_date == today:
            add_to_summary(periods["today"], trip)

        if trip_date >= week_start:
            add_to_summary(periods["week"], trip)

        if trip_date >= month_start:
            add_to_summary(periods["month"], trip)

        if trip_date >= year_start:
            add_to_summary(periods["year"], trip)

        year_obj = tree.setdefault(
            year_key,
            {
                "summary": empty_summary(),
                "months": {},
            },
        )

        month_obj = year_obj["months"].setdefault(
            month_key,
            {
                "name": month_name_it(start_dt.month),
                "summary": empty_summary(),
                "days": {},
            },
        )

        day_obj = month_obj["days"].setdefault(
            day_key,
            {
                "label": start_dt.strftime("%d/%m/%Y"),
                "summary": empty_summary(),
                "trips": [],
            },
        )

        day_obj["trips"].append(trip)

        add_to_summary(year_obj["summary"], trip)
        add_to_summary(month_obj["summary"], trip)
        add_to_summary(day_obj["summary"], trip)

    output = {
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "latest_trip": latest_trip,
        "summary": periods,
        "tree": tree,
        "trips": flat_trips,
    }

    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    conn.close()


if __name__ == "__main__":
    main()