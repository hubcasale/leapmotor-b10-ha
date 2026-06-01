#!/usr/bin/env python3
"""
Geocode an address via Nominatim and update HA input entities,
then optionally send the destination to the Leapmotor navigation.

Usage:
    python3 geocode_destination.py "Via Torino 10" "Milano"
"""

import re
import sys
import json
import urllib.request
import urllib.parse
import yaml

SKIP_WORDS = {
    "via", "corso", "piazza", "viale", "vicolo", "largo", "strada",
    "del", "della", "dei", "degli", "delle", "di", "il", "la", "lo",
    "le", "gli", "i", "un", "una", "al", "alla", "sul", "sulla",
}

def street_matches(input_address, result_street):
    """Verifica che almeno una parola chiave della via di input sia nel risultato."""
    if not result_street:
        return False
    words = [w for w in re.findall(r"[a-zàèéìòùü]+", input_address.lower())
             if w not in SKIP_WORDS and len(w) > 3]
    if not words:
        return True
    result_lower = result_street.lower()
    return all(w in result_lower for w in words)

HA_URL = "http://localhost:8123"
SECRETS_PATH = "/config/secrets.yaml"


def get_token():
    with open(SECRETS_PATH) as f:
        secrets = yaml.safe_load(f)
    return secrets.get("appdaemon_token", "")


def ha_set_state(token, entity_id, state, attributes=None):
    url = f"{HA_URL}/api/states/{entity_id}"
    payload = {"state": str(state)}
    if attributes:
        payload["attributes"] = attributes
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status


def ha_call_service(token, domain, service, data):
    url = f"{HA_URL}/api/services/{domain}/{service}"
    payload = json.dumps(data).encode()
    req = urllib.request.Request(
        url, data=payload, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status


def geocode(address, city=""):
    query = " ".join(p for p in [address, city] if p)
    q_encoded = urllib.parse.quote_plus(query)
    url = f"https://photon.komoot.io/api/?q={q_encoded}&limit=5"
    req = urllib.request.Request(url, headers={"User-Agent": "HomeAssistant-Leapmotor/1.0"})
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    features = data.get("features", [])
    if not features:
        return []
    # Filtra per città corrispondente
    if city:
        city_lower = city.strip().lower()
        features = [
            f for f in features
            if (f["properties"].get("city") or f["properties"].get("town") or "").lower() == city_lower
        ]
        if not features:
            return []
    # Filtra per corrispondenza via: almeno una parola chiave dell'input nel risultato
    features = [f for f in features if street_matches(address, f["properties"].get("street", ""))]
    if not features:
        return []
    feat = features[0]
    props = feat["properties"]
    coords = feat["geometry"]["coordinates"]
    parts = [
        props.get("housenumber", ""),
        props.get("street", "") or props.get("name", ""),
        props.get("city", "") or props.get("town", "") or props.get("village", ""),
        props.get("state", ""),
        props.get("postcode", ""),
        props.get("country", ""),
    ]
    display_name = ", ".join(p for p in parts if p)
    return [{"lat": coords[1], "lon": coords[0], "display_name": display_name}]


def main():
    if len(sys.argv) < 2:
        print("Usage: geocode_destination.py <query>")
        sys.exit(1)

    address = sys.argv[1].strip()
    city = sys.argv[2].strip() if len(sys.argv) > 2 else ""
    token = get_token()

    # Imposta stato "searching"
    ha_set_state(token, "input_text.leapmotor_nav_status", "searching")
    ha_set_state(token, "input_text.leapmotor_nav_label", "Ricerca in corso...")

    try:
        results = geocode(address, city)
    except Exception as e:
        ha_set_state(token, "input_text.leapmotor_nav_status", "error")
        ha_set_state(token, "input_text.leapmotor_nav_label", f"Errore connessione: {e}")
        sys.exit(1)

    if not results:
        ha_set_state(token, "input_text.leapmotor_nav_status", "not_found")
        msg = f"Non trovato a {city}" if city else "Indirizzo non trovato"
        ha_set_state(token, "input_text.leapmotor_nav_label", msg)
        sys.exit(1)

    result = results[0]
    lat = float(result["lat"])
    lon = float(result["lon"])
    label = result.get("display_name", f"{address}, {city}")
    label = label[:200]

    ha_set_state(token, "input_number.leapmotor_nav_lat", lat)
    ha_set_state(token, "input_number.leapmotor_nav_lon", lon)
    ha_set_state(token, "input_text.leapmotor_nav_label", label)
    ha_set_state(token, "input_text.leapmotor_nav_status", "found")

    # Aggiorna device_tracker per la map card nativa HA
    ha_set_state(token, "device_tracker.leapmotor_nav_destination", "home", {
        "latitude": lat,
        "longitude": lon,
        "gps_accuracy": 10,
        "friendly_name": label[:50]
    })

    print(f"OK: {label} ({lat}, {lon})")


if __name__ == "__main__":
    main()
