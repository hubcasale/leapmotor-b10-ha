import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

TRIP_FILE = Path("/config/leapmotor/trip_log.json")
DB_FILE = Path("/config/leapmotor/leapmotor_trip.db")


def safe_float(value, default=0.0):
    try:
        return float(value)
    except Exception:
        return default


def parse_datetime(value):
    """
    Formato atteso: YYYY-MM-DD HH:MM:SS
    """
    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def format_duration(start_value, end_value):
    """
    Calcola durata reale da start/end.
    Ritorna formato HH:MM.
    """
    start_dt = parse_datetime(start_value)
    end_dt = parse_datetime(end_value)

    if not start_dt or not end_dt:
        return "00:00", 0

    seconds = int((end_dt - start_dt).total_seconds())

    if seconds <= 0:
        return "00:00", 0

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    return f"{hours:02d}:{minutes:02d}", seconds


def calculate_average_speed(km, duration_seconds):
    """
    Calcola velocità media da km e durata reale.
    """
    if km <= 0 or duration_seconds <= 0:
        return 0.0

    hours = duration_seconds / 3600.0
    return round(km / hours, 1)


# --------------------------
# CONTROLLO ARGOMENTI
# --------------------------
if len(sys.argv) < 13:
    print("Errore: argomenti insufficienti")
    print(f"Ricevuti {len(sys.argv) - 1} argomenti, attesi 12")
    sys.exit(1)


# --------------------------
# DATI DA STOP TRIP
# --------------------------
start = sys.argv[1]
end = sys.argv[2]

km_start = round(safe_float(sys.argv[4]), 1)
km_end = round(safe_float(sys.argv[5]), 1)
km = round(safe_float(sys.argv[6]), 1)

kwh = round(safe_float(sys.argv[7]), 2)
cons = round(safe_float(sys.argv[8]), 1)

soc_start = round(safe_float(sys.argv[9]), 1)
soc_end = round(safe_float(sys.argv[10]), 1)

temperatura = round(safe_float(sys.argv[12]), 1)

# Calcolo robusto interno
durata, duration_seconds = format_duration(start, end)
vel_media = calculate_average_speed(km, duration_seconds)


trip_data = {
    "start": start,
    "end": end,
    "durata": durata,

    "km_start": km_start,
    "km_end": km_end,
    "km": km,

    "kwh": kwh,
    "cons": cons,

    "soc_start": soc_start,
    "soc_end": soc_end,

    "vel_media": vel_media,
    "temperatura": temperatura,

    "note": ""
}


# --------------------------
# SALVATAGGIO JSON BACKUP
# --------------------------
if TRIP_FILE.exists():
    with open(TRIP_FILE, "r", encoding="utf-8") as f:
        try:
            trips = json.load(f)
        except Exception:
            trips = []
else:
    trips = []

trips.append(trip_data)

with open(TRIP_FILE, "w", encoding="utf-8") as f:
    json.dump(
        trips,
        f,
        ensure_ascii=False,
        indent=2
    )


# --------------------------
# SALVATAGGIO SQLITE
# --------------------------
conn = sqlite3.connect(DB_FILE)
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS trips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,

        start TEXT,
        end TEXT,
        durata TEXT,

        km_start REAL,
        km_end REAL,
        km REAL,

        kwh REAL,
        cons REAL,

        soc_start REAL,
        soc_end REAL,

        vel_media REAL,
        temperatura REAL,

        note TEXT
    )
""")

cursor.execute("""
    INSERT INTO trips (
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
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", (
    trip_data["start"],
    trip_data["end"],
    trip_data["durata"],
    trip_data["km_start"],
    trip_data["km_end"],
    trip_data["km"],
    trip_data["kwh"],
    trip_data["cons"],
    trip_data["soc_start"],
    trip_data["soc_end"],
    trip_data["vel_media"],
    trip_data["temperatura"],
    trip_data["note"]
))

conn.commit()
conn.close()

print(
    f"Trip salvato su JSON + SQLite | durata={durata} | vel_media={vel_media} km/h"
)