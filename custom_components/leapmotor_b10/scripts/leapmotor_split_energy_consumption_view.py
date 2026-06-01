#!/usr/bin/env python3

import json
import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path

DASHBOARD = Path("/config/.storage/lovelace.leapmotor_b10")

NEW_VIEW_PATH = "leapmotor-consumi"
ENERGY_VIEW_PATH = "leapmotor-energy"

NEW_VIEW = {
    "title": "Consumi EV",
    "path": NEW_VIEW_PATH,
    "icon": "mdi:chart-line",
    "type": "sections",
    "max_columns": 3,
    "sections": [],
    "cards": [],
}


def card_title(card):
    if not isinstance(card, dict):
        return None

    if card.get("type") == "custom:mushroom-title-card":
        return card.get("title")

    if card.get("type") == "vertical-stack":
        cards = card.get("cards", [])
        if cards and isinstance(cards[0], dict):
            if cards[0].get("type") == "custom:mushroom-title-card":
                return cards[0].get("title")

    return None


def is_vertical_stack_title(card, title):
    return isinstance(card, dict) and card.get("type") == "vertical-stack" and card_title(card) == title


def find_first_title_index(cards, titles):
    for idx, card in enumerate(cards):
        if isinstance(card, dict) and card.get("type") == "custom:mushroom-title-card":
            if card.get("title") in titles:
                return idx
    return None


def process_cards(cards, extracted):
    """
    Lavora ricorsivamente sulle liste cards:
    - rimuove lo stack Energy Summary / Mileage Summary da Energy
    - divide lo stack Ultima ricarica lasciando in Energy solo la parte ricarica
    - estrae Dalla precedente ricarica + Dall'ultima ricarica completata
    """
    if not isinstance(cards, list):
        return cards

    new_cards = []

    for card in cards:
        if not isinstance(card, dict):
            new_cards.append(card)
            continue

        title = card_title(card)

        # Sposta tutto lo stack Energy Summary, che contiene anche Mileage Summary
        if is_vertical_stack_title(card, "Energy Summary"):
            extracted["energy_summary"] = deepcopy(card)
            continue

        # Divide lo stack Ultima ricarica
        if is_vertical_stack_title(card, "Ultima ricarica"):
            stack_cards = card.get("cards", [])

            split_idx = find_first_title_index(
                stack_cards,
                {
                    "Dalla precedente ricarica",
                    "Dall’ultima ricarica completata",
                    "Dall'ultima ricarica completata",
                },
            )

            if split_idx is not None:
                consumption_part = deepcopy(stack_cards[split_idx:])
                extracted["charge_consumption_cards"] = consumption_part

                kept = deepcopy(card)
                kept["cards"] = stack_cards[:split_idx]
                new_cards.append(kept)
                continue

        # Ricorsione su eventuali cards interne
        changed = deepcopy(card)
        if "cards" in changed and isinstance(changed["cards"], list):
            changed["cards"] = process_cards(changed["cards"], extracted)

        new_cards.append(changed)

    return new_cards


def main():
    if not DASHBOARD.exists():
        raise SystemExit(f"ERRORE: file non trovato: {DASHBOARD}")

    backup = DASHBOARD.with_name(
        DASHBOARD.name + ".bak_split_consumi_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    shutil.copy2(DASHBOARD, backup)

    data = json.loads(DASHBOARD.read_text())

    views = data.get("data", {}).get("config", {}).get("views")
    if not isinstance(views, list):
        raise SystemExit("ERRORE: struttura dashboard non valida: data.config.views non trovato")

    if any(v.get("path") == NEW_VIEW_PATH for v in views if isinstance(v, dict)):
        raise SystemExit(f"ERRORE: esiste già una vista con path '{NEW_VIEW_PATH}'. Nessuna modifica fatta.")

    energy_view = None
    for view in views:
        if isinstance(view, dict) and view.get("path") == ENERGY_VIEW_PATH:
            energy_view = view
            break

    if energy_view is None:
        raise SystemExit(f"ERRORE: vista '{ENERGY_VIEW_PATH}' non trovata")

    extracted = {
        "energy_summary": None,
        "charge_consumption_cards": None,
    }

    sections = energy_view.get("sections", [])
    if not isinstance(sections, list):
        raise SystemExit("ERRORE: la vista Energy non contiene sections valide")

    new_sections = []
    for section in sections:
        changed_section = deepcopy(section)

        if "cards" in changed_section and isinstance(changed_section["cards"], list):
            changed_section["cards"] = process_cards(changed_section["cards"], extracted)

        new_sections.append(changed_section)

    energy_view["sections"] = new_sections

    # Costruzione nuova vista Consumi EV
    consumption_sections = []

    if extracted["charge_consumption_cards"]:
        consumption_sections.append({
            "type": "grid",
            "cards": [
                {
                    "type": "vertical-stack",
                    "cards": extracted["charge_consumption_cards"],
                }
            ],
        })

    if extracted["energy_summary"]:
        consumption_sections.append({
            "type": "grid",
            "cards": [
                extracted["energy_summary"]
            ],
        })

    if not consumption_sections:
        raise SystemExit(
            "ERRORE: non ho trovato blocchi consumi da spostare. "
            f"Backup creato: {backup}"
        )

    new_view = deepcopy(NEW_VIEW)
    new_view["sections"] = consumption_sections

    # Inserisce Consumi EV subito dopo Energy
    energy_index = views.index(energy_view)
    views.insert(energy_index + 1, new_view)

    DASHBOARD.write_text(json.dumps(data, ensure_ascii=False, indent=2))

    print("OK: dashboard modificata")
    print(f"Backup: {backup}")
    print(f"Nuova vista: {NEW_VIEW_PATH}")
    print("Blocchi spostati:")
    print(f"- Dati ricariche/consumi: {'OK' if extracted['charge_consumption_cards'] else 'NO'}")
    print(f"- Energy Summary / Mileage Summary: {'OK' if extracted['energy_summary'] else 'NO'}")


if __name__ == "__main__":
    main()
