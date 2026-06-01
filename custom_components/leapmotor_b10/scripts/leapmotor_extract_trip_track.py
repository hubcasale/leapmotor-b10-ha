#!/usr/bin/env python3

import json
import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, "/config/deps")
import pymysql


TRIP_DB = "/config/leapmotor/leapmotor_trip.db"
OUTPUT_DIR = Path("/config/www/leapmotor/tracks")
OUTPUT_SELECTED = Path("/config/www/leapmotor/selected_trip_track.geojson")

MARIADB_HOST = os.environ.get("MARIADB_HOST", "core-mariadb")
MARIADB_USER = os.environ.get("MARIADB_USER", "homeassistant")
MARIADB_PASSWORD = os.environ.get("MARIADB_PASSWORD", "")
MARIADB_DB = os.environ.get("MARIADB_DB", "homeassistant")

ENTITY_ID = "device_tracker.leapmotor_location"


def parse_args():
    if len(sys.argv) >= 2:
        try:
            return int(sys.argv[1])
        except ValueError:
            print(f"ERRORE: trip_id non valido: {sys.argv[1]}")
            sys.exit(1)
    return None


def get_trip(trip_id=None):
    if not os.path.exists(TRIP_DB):
        raise FileNotFoundError(f"DB viaggi non trovato: {TRIP_DB}")

    conn = sqlite3.connect(TRIP_DB)
    conn.row_factory = sqlite3.Row

    try:
        if trip_id is None:
            row = conn.execute(
                """
                SELECT id, start, end, durata, km, kwh, cons, soc_start, soc_end, vel_media, temperatura
                FROM trips
                WHERE start IS NOT NULL
                  AND end IS NOT NULL
                  AND end != ''
                ORDER BY id DESC
                LIMIT 1
                """
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT id, start, end, durata, km, kwh, cons, soc_start, soc_end, vel_media, temperatura
                FROM trips
                WHERE id = ?
                """,
                (trip_id,),
            ).fetchone()
    finally:
        conn.close()

    if row is None:
        raise RuntimeError("Nessun viaggio valido trovato")

    return dict(row)


def read_points_from_mariadb(start, end):
    sql = """
SELECT
  FROM_UNIXTIME(s.last_updated_ts) AS ts,
  s.state,
  JSON_UNQUOTE(JSON_EXTRACT(sa.shared_attrs, '$.raw_latitude')) AS raw_latitude,
  JSON_UNQUOTE(JSON_EXTRACT(sa.shared_attrs, '$.raw_longitude')) AS raw_longitude,
  JSON_UNQUOTE(JSON_EXTRACT(sa.shared_attrs, '$.location_source')) AS location_source,
  JSON_UNQUOTE(JSON_EXTRACT(sa.shared_attrs, '$.location_is_stale')) AS location_is_stale,
  JSON_UNQUOTE(JSON_EXTRACT(sa.shared_attrs, '$.location_age_seconds')) AS location_age_seconds
FROM states s
JOIN states_meta sm ON sm.metadata_id = s.metadata_id
LEFT JOIN state_attributes sa ON sa.attributes_id = s.attributes_id
WHERE sm.entity_id = %s
  AND s.last_updated_ts BETWEEN UNIX_TIMESTAMP(%s)
                            AND UNIX_TIMESTAMP(%s)
  AND JSON_UNQUOTE(JSON_EXTRACT(sa.shared_attrs, '$.raw_latitude')) IS NOT NULL
  AND JSON_UNQUOTE(JSON_EXTRACT(sa.shared_attrs, '$.raw_longitude')) IS NOT NULL
ORDER BY s.last_updated_ts ASC;
"""

    conn = pymysql.connect(
        host=MARIADB_HOST,
        user=MARIADB_USER,
        password=MARIADB_PASSWORD,
        database=MARIADB_DB,
        charset="utf8mb4",
        autocommit=True,
    )

    try:
        with conn.cursor() as cur:
            cur.execute(sql, (ENTITY_ID, start, end))
            rows = cur.fetchall()
    finally:
        conn.close()

    return rows


def parse_points(rows):
    points = []
    seen = set()

    for row in rows:
        if len(row) < 7:
            continue

        ts, state, lat_raw, lon_raw, source, stale, age_raw = row[:7]

        try:
            lat = float(lat_raw)
            lon = float(lon_raw)
        except (TypeError, ValueError):
            continue

        if lat == 0 or lon == 0:
            continue

        if source != "cloud":
            continue

        if str(stale).lower() == "true":
            continue

        key = (round(lat, 7), round(lon, 7), str(ts))
        if key in seen:
            continue
        seen.add(key)

        try:
            age = int(float(age_raw))
        except (TypeError, ValueError):
            age = None

        points.append(
            {
                "timestamp": str(ts),
                "state": state,
                "latitude": lat,
                "longitude": lon,
                "location_source": source,
                "location_age_seconds": age,
            }
        )

    return points


def build_geojson(trip, points):
    coordinates = [[p["longitude"], p["latitude"]] for p in points]
    features = []

    if len(coordinates) >= 2:
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "type": "route",
                    "trip_id": trip["id"],
                    "start": trip["start"],
                    "end": trip["end"],
                    "duration": trip.get("durata"),
                    "km": trip.get("km"),
                    "kwh": trip.get("kwh"),
                    "cons": trip.get("cons"),
                    "soc_start": trip.get("soc_start"),
                    "soc_end": trip.get("soc_end"),
                    "vel_media": trip.get("vel_media"),
                    "temperatura": trip.get("temperatura"),
                    "points": len(points),
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordinates,
                },
            }
        )

    if points:
        first = points[0]
        last = points[-1]

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "type": "start",
                    "label": "Partenza",
                    "timestamp": first["timestamp"],
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [first["longitude"], first["latitude"]],
                },
            }
        )

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "type": "end",
                    "label": "Arrivo",
                    "timestamp": last["timestamp"],
                },
                "geometry": {
                    "type": "Point",
                    "coordinates": [last["longitude"], last["latitude"]],
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "properties": {
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "trip_id": trip["id"],
            "start": trip["start"],
            "end": trip["end"],
            "duration": trip.get("durata"),
            "km": trip.get("km"),
            "kwh": trip.get("kwh"),
            "cons": trip.get("cons"),
            "soc_start": trip.get("soc_start"),
            "soc_end": trip.get("soc_end"),
            "vel_media": trip.get("vel_media"),
            "temperatura": trip.get("temperatura"),
            "points": len(points),
        },
        "features": features,
    }


def save_outputs(trip, geojson):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    trip_file = OUTPUT_DIR / f"trip_{trip['id']}.geojson"

    with trip_file.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    with OUTPUT_SELECTED.open("w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    return trip_file


def main():
    trip_id = parse_args()
    trip = get_trip(trip_id)

    print(
        f"Viaggio selezionato: id={trip['id']} "
        f"start={trip['start']} end={trip['end']} km={trip.get('km')}"
    )

    rows = read_points_from_mariadb(trip["start"], trip["end"])
    print(f"Righe recorder lette: {len(rows)}")

    points = parse_points(rows)
    print(f"Punti GPS validi trovati: {len(points)}")

    geojson = build_geojson(trip, points)
    trip_file = save_outputs(trip, geojson)

    print(f"File viaggio: {trip_file}")
    print(f"File selezionato: {OUTPUT_SELECTED}")

    if len(points) < 2:
        print("ATTENZIONE: pochi punti GPS validi, percorso non disegnabile come linea.")
        sys.exit(2)


if __name__ == "__main__":
    main()
