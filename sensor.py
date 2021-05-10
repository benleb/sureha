"""Support for Sure PetCare Flaps/Pets sensors."""
from __future__ import annotations

import logging

from pprint import pformat
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import (
    ATTR_VOLTAGE,
    DEVICE_CLASS_BATTERY,
    MASS_GRAMS,
    PERCENTAGE,
    VOLUME_MILLILITERS,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from surepy.entities import SurepyEntity
from surepy.entities.devices import Feeder as SureFeeder, FeederBowl as SureFeederBowl
from surepy.enums import EntityType, LockState

from . import SurePetcareAPI
from .const import (
    DOMAIN,
    SPC,
    SURE_BATT_VOLTAGE_DIFF,
    SURE_BATT_VOLTAGE_LOW,
    TOPIC_UPDATE,
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: Any, config: dict[str, Any], async_add_entities: Any, discovery_info: Any = None
) -> None:
    """Set up Sure PetCare Flaps sensors."""
    if discovery_info is None:
        return

    entities: list[SurepyEntity] = []

    spc: SurePetcareAPI = hass.data[DOMAIN][SPC]

    for surepy_entity in spc.states.values():

        _LOGGER.info("🐾 %s -- %s", surepy_entity.name, surepy_entity.type)

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ]:
            entities.append(SureBattery(surepy_entity.id, spc))

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
        ]:
            entities.append(Flap(surepy_entity.id, spc))

        if surepy_entity.type == EntityType.FELAQUA:
            entities.append(Felaqua(surepy_entity.id, spc))

        if surepy_entity.type == EntityType.FEEDER:
            entities.append(Feeder(surepy_entity.id, spc))
            for bowl in surepy_entity.bowls.values():
                entities.append(FeederBowl(surepy_entity.id, spc, bowl.raw_data()))

    async_add_entities(entities)


class SurePetcareSensor(SensorEntity):  # type: ignore
    """A binary sensor implementation for Sure Petcare Entities."""

    def __init__(self, _id: int, spc: SurePetcareAPI):
        """Initialize a Sure Petcare sensor."""

        self._id = _id
        self._spc: SurePetcareAPI = spc

        self._surepy_entity: SurepyEntity = self._spc.states[_id]
        self._state: dict[str, Any] = {}
        self._name = (
            f"{self._surepy_entity.type.name.replace('_', ' ').title()} "
            f"{self._surepy_entity.name.capitalize()}"
        )

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self._name} "

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._surepy_entity.household_id}-{self._id}"

    @property
    def available(self) -> bool:
        """Return true if entity is available."""
        return bool(self._state)

    @property
    def should_poll(self) -> bool:
        """Return true."""
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {**self._surepy_entity.raw_data()}

        return attributes

    @callback  # type: ignore
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        self._surepy_entity = self._spc.states[self._id]
        self._state = self._surepy_entity.raw_data()["status"]
        _LOGGER.debug(
            "🐾 %s updated to: %s", self._surepy_entity.name, pformat(self._state, indent=4)
        )

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""

        self.async_on_remove(async_dispatcher_connect(self.hass, TOPIC_UPDATE, self._async_update))

        @callback  # type: ignore
        def update() -> None:
            """Update the state."""
            self.async_schedule_update_ha_state(True)

        self._async_unsub_dispatcher_connect = async_dispatcher_connect(
            self.hass, TOPIC_UPDATE, update
        )

        self._async_update()


class Flap(SurePetcareSensor):
    """Sure Petcare Flap."""

    @property
    def state(self) -> str:
        """Return battery level in percent."""
        return LockState(self._state["locking"]["mode"]).name.replace("_", " ").title()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {
                "learn_mode": bool(self._state["learn_mode"]),
                **self._surepy_entity.raw_data(),
            }

        return attributes


class Felaqua(SurePetcareSensor):
    """Sure Petcare Felaqua."""

    @property
    def state(self) -> int | None:
        """Return the remaining water."""
        self._surepy_entity: Felaqua
        return int(self._surepy_entity.water_remaining)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return str(VOLUME_MILLILITERS)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the device."""
        attributes = None
        if self._state:
            attributes = {**self._surepy_entity.raw_data()}

        return attributes


class FeederBowl(SurePetcareSensor):
    """Sure Petcare Feeder Bowl."""

    def __init__(self, _id: int, spc: SurePetcareAPI, bowl_data: dict[str, int | str]):
        """Initialize a Sure Petcare sensor."""

        self.feeder_id = _id
        self.bowl_id = int(bowl_data["index"])

        self._id = int(f"{_id}{str(self.bowl_id)}")
        self._spc: SurePetcareAPI = spc

        self._surepy_feeder_entity: SurepyEntity = self._spc.states[_id]
        self._surepy_entity: SurepyEntity = self._spc.states[_id].bowls[self.bowl_id]
        self._state: dict[str, Any] = bowl_data

        # self._name = (
        #     f"{self._surepy_feeder_entity.type.name.replace('_', ' ').title()} "
        #     f"{self._surepy_feeder_entity.name.capitalize()} "
        #     f"Bowl {self._surepy_entity.position}"
        # )

        self._name = self._surepy_entity.name

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._surepy_feeder_entity.household_id}-{self.feeder_id}-{self.bowl_id}"

    @property
    def state(self) -> int | None:
        """Return the remaining water."""
        self._surepy_entity: SureFeederBowl
        return int(self._surepy_entity.weight)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return str(MASS_GRAMS)

    @callback  # type: ignore
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        self._surepy_feeder_entity = self._spc.states[self.feeder_id]
        self._surepy_entity = self._spc.states[self.feeder_id].bowls[self.bowl_id]
        self._state = self._surepy_entity.raw_data()
        _LOGGER.debug(
            "🐾 %s updated to: %s", self._surepy_entity.name, pformat(self._state, indent=4)
        )


class Feeder(SurePetcareSensor):
    """Sure Petcare Felaqua."""

    @property
    def state(self) -> int | None:
        """Return the total remaining food."""
        self._surepy_entity: SureFeeder
        return int(self._surepy_entity.total_weight)

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return str(MASS_GRAMS)

    @callback  # type: ignore
    def _async_update(self) -> None:
        """Get the latest data and update the state."""
        self._surepy_entity = self._spc.states[self._id]
        self._state = self._surepy_entity.raw_data()["status"]

        for bowl_data in self._surepy_entity.raw_data()["lunch"]["weights"]:
            self._surepy_entity.bowls[bowl_data["index"]]._data = bowl_data

        _LOGGER.debug(
            "🐾 %s updated to: %s", self._surepy_entity.name, pformat(self._state, indent=4)
        )


class SureBattery(SurePetcareSensor):
    """Sure Petcare Flap."""

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        return f"{self._name} Battery Level"

    @property
    def state(self) -> int | None:
        """Return battery level in percent."""
        battery_percent: int | None
        try:
            per_battery_voltage = self._state["battery"] / 4
            voltage_diff = per_battery_voltage - SURE_BATT_VOLTAGE_LOW
            battery_percent = min(int(voltage_diff / SURE_BATT_VOLTAGE_DIFF * 100), 100)
        except (KeyError, TypeError):
            battery_percent = None

        return battery_percent

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return f"{self._surepy_entity.household_id}-{self._surepy_entity.id}-battery"

    @property
    def device_class(self) -> str:
        """Return the device class."""
        return str(DEVICE_CLASS_BATTERY)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return state attributes."""
        attributes = None
        if self._state:
            voltage_per_battery = float(self._state["battery"]) / 4
            attributes = {
                ATTR_VOLTAGE: f"{float(self._state['battery']):.2f}",
                f"{ATTR_VOLTAGE}_per_battery": f"{voltage_per_battery:.2f}",
            }

        return attributes

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return str(PERCENTAGE)
