"""Sensor platform for Leapmotor B10."""
from __future__ import annotations

import os
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.components.command_line.sensor import CommandLineSensor

from .const import DOMAIN, CONF_ENTRY_ID

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    
    # Sensore per la cronologia viaggi (History)
    # Usiamo la logica del command_line sensor che abbiamo corretto prima
    trip_history_sensor = {
        "name": "Leapmotor Trip History",
        "command": "cat /config/www/leapmotor/trip_summary.json",
        "unit_of_measurement": None,
        "value_template": "{{ value_json.generated_at | default('N/D') }}",
        "json_attributes": ["trips"],
        "unique_id": f"leapmotor_trip_history_{entry.entry_id}",
    }
    
    # In una versione più avanzata, qui creeremmo entità native.
    # Per ora lasciamo che il pacchetto YAML continui a funzionare 
    # ma prepariamo il terreno per la migrazione completa.
    
    pass
