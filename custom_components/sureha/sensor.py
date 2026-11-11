"""Support for Sure PetCare Flaps/Pets sensors."""

from __future__ import annotations

import logging
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_VOLTAGE, PERCENTAGE, UnitOfMass, UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from surepy.entities import SurepyEntity
from surepy.entities.devices import (
    Feeder as SureFeeder,
    Felaqua as SureFelaqua,
    SurepyDevice,
)
from surepy.enums import BowlPosition, EntityType, LockState

# pylint: disable=relative-beyond-top-level
from . import SurePetcareAPI
from .const import (
    ATTR_VOLTAGE_FULL,
    ATTR_VOLTAGE_LOW,
    DOMAIN,
    SPC,
    SURE_BATT_VOLTAGE_FULL,
    SURE_BATT_VOLTAGE_LOW,
    SURE_MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 2

NUM_BATTERIES = 4


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up config entry Sure PetCare Flaps sensors."""

    entities: list[SurePetcareSensor] = []

    spc: SurePetcareAPI = hass.data[DOMAIN][SPC]

    voltage_full = float(
        config_entry.options.get(ATTR_VOLTAGE_FULL, SURE_BATT_VOLTAGE_FULL)
    )
    voltage_low = float(config_entry.options.get(ATTR_VOLTAGE_LOW, SURE_BATT_VOLTAGE_LOW))

    for surepy_entity in spc.entities:

        status = surepy_entity.raw_data().get("status") or {}

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
        ] and status.get("locking"):
            entities.append(Flap(spc.coordinator, surepy_entity.id, spc))

        elif surepy_entity.type == EntityType.FELAQUA:
            entities.append(Felaqua(spc.coordinator, surepy_entity.id, spc))

        elif surepy_entity.type == EntityType.FEEDER:

            # bowl configuration: one entry per bowl (index 0 = left, 1 = right)
            control = surepy_entity.raw_data().get("control") or {}
            bowl_settings = (control.get("bowls") or {}).get("settings") or []
            bowl_indexes = set(range(len(bowl_settings)))

            # bowls reported with weights by surepy
            bowl_indexes.update(cast(SureFeeder, surepy_entity).bowls.keys())

            _LOGGER.debug(
                "%s | bowls: %s", surepy_entity.name, sorted(bowl_indexes)
            )

            for bowl_index in sorted(bowl_indexes):
                entities.append(
                    FeederBowl(spc.coordinator, surepy_entity.id, spc, bowl_index)
                )

            entities.append(Feeder(spc.coordinator, surepy_entity.id, spc))

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ] and status.get("battery"):
            entities.append(
                Battery(
                    spc.coordinator,
                    surepy_entity.id,
                    spc,
                    voltage_full=voltage_full,
                    voltage_low=voltage_low,
                )
            )

    async_add_entities(entities)


class SurePetcareSensor(CoordinatorEntity, SensorEntity):
    """A sensor implementation for Sure Petcare Entities."""

    _attr_should_poll = False

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI):
        """Initialize a Sure Petcare sensor."""
        super().__init__(coordinator)

        self._id = _id
        self._spc: SurePetcareAPI = spc

        self._coordinator = coordinator

        self._surepy_entity: SurepyEntity = self._coordinator.data[_id]
        self._state: dict[str, Any] = self._surepy_entity.raw_data().get("status") or {}

        self._attr_unique_id = f"{self._surepy_entity.household_id}-{self._id}"

        type_name = self._surepy_entity.type.name.replace("_", " ").title()
        name = self._surepy_entity.name or f"Unnamed {type_name}"
        self._name = name.capitalize()

        self._attr_name = f"{type_name} {self._name}"

    @property
    def _data(self) -> SurepyEntity | None:
        """Return the current surepy entity from the coordinator."""
        return self._coordinator.data.get(self._id) if self._coordinator.data else None

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        return (
            super().available
            and (entity := self._data) is not None
            and bool(entity.raw_data().get("status"))
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the additional attrs."""
        if entity := self._data:
            return {**entity.raw_data()}
        return {}

    @property
    def device_info(self):
        """Return the device info."""

        device = {}

        try:

            model = f"{self._surepy_entity.type.name.replace('_', ' ').title()}"
            if serial := self._surepy_entity.raw_data().get("serial_number"):
                model = f"{model} ({serial})"
            elif mac_address := self._surepy_entity.raw_data().get("mac_address"):
                model = f"{model} ({mac_address})"
            elif tag_id := self._surepy_entity.raw_data().get("tag_id"):
                model = f"{model} ({tag_id})"

            device = {
                "identifiers": {(DOMAIN, self._id)},
                "name": self._name,
                "manufacturer": SURE_MANUFACTURER,
                "model": model,
            }

            if self._state:
                versions = self._state.get("version", {})

                if dev_fw_version := versions.get("device", {}).get("firmware"):
                    device["sw_version"] = dev_fw_version

                if (lcd_version := versions.get("lcd", {})) and (
                    rf_version := versions.get("rf", {})
                ):
                    device["sw_version"] = (
                        f"lcd: {lcd_version.get('version', lcd_version)['firmware']} | "
                        f"fw: {rf_version.get('version', rf_version)['firmware']}"
                    )

        except (AttributeError, KeyError, TypeError):
            pass

        return device


class Flap(SurePetcareSensor):
    """Sure Petcare Flap."""

    _attr_icon = "mdi:door"

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI) -> None:
        """Initialize a Sure Petcare flap sensor."""
        super().__init__(coordinator, _id, spc)

        self._attr_entity_picture = getattr(self._surepy_entity, "icon", None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the additional attrs."""
        attrs = super().extra_state_attributes

        if (entity := self._data) and (status := entity.raw_data().get("status")):
            attrs = {"learn_mode": bool(status.get("learn_mode")), **attrs}

        return attrs

    @property
    def native_value(self) -> str | None:
        """Return the lock state of the flap."""

        if not (entity := self._data):
            return None

        status = entity.raw_data().get("status") or {}
        mode = (status.get("locking") or {}).get("mode")

        try:
            return LockState(mode).name.casefold() if mode is not None else None
        except ValueError:
            _LOGGER.debug("unknown lock mode for flap %s: %s", self._id, mode)
            return None


class Felaqua(SurePetcareSensor):
    """Sure Petcare Felaqua."""

    _attr_native_unit_of_measurement = UnitOfVolume.MILLILITERS
    _attr_device_class = SensorDeviceClass.VOLUME_STORAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI):
        """Initialize a Sure Petcare Felaqua sensor."""
        super().__init__(coordinator, _id, spc)

        self._attr_entity_picture = getattr(self._surepy_entity, "icon", None)

    @property
    def native_value(self) -> int | None:
        """Return the remaining water."""
        if (felaqua := cast(SureFelaqua, self._data)) and (
            remaining := felaqua.water_remaining
        ) is not None:
            return int(remaining)
        return None


class FeederBowl(SurePetcareSensor):
    """Sure Petcare Feeder Bowl."""

    _attr_icon = "mdi:bowl"
    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator,
        _id: int,
        spc: SurePetcareAPI,
        bowl_index: int,
    ):
        """Initialize a Bowl sensor."""
        super().__init__(coordinator, _id, spc)

        self.bowl_index = bowl_index

        try:
            position = BowlPosition(bowl_index).name.title()
        except ValueError:
            position = str(bowl_index)

        self._attr_name = f"{self._attr_name} Bowl {position}"
        self._attr_unique_id = (
            f"{self._surepy_entity.household_id}-{self._id}-bowl-{bowl_index}"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the additional attrs."""
        if (feeder := cast(SureFeeder, self._data)) and (
            bowl := feeder.bowls.get(self.bowl_index)
        ):
            return {"bowl_index": self.bowl_index, **bowl.raw_data()}
        return {"bowl_index": self.bowl_index}

    @property
    def native_value(self) -> int | None:
        """Return the remaining food in the bowl."""

        if (feeder := cast(SureFeeder, self._data)) and (
            bowl := feeder.bowls.get(self.bowl_index)
        ):
            try:
                weight = bowl.weight
            except (KeyError, TypeError, ValueError):
                return None

            return int(weight) if weight > 0 else 0

        return None


class Feeder(SurePetcareSensor):
    """Sure Petcare Feeder."""

    _attr_native_unit_of_measurement = UnitOfMass.GRAMS
    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI):
        """Initialize a Sure Petcare feeder sensor."""
        super().__init__(coordinator, _id, spc)

        self._attr_entity_picture = getattr(self._surepy_entity, "icon", None)

    @property
    def native_value(self) -> int | None:
        """Return the total remaining food."""
        if feeder := cast(SureFeeder, self._data):
            try:
                return int(feeder.total_weight)
            except (KeyError, TypeError, ValueError):
                return None
        return None


class Battery(SurePetcareSensor):
    """Sure Petcare device battery."""

    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator,
        _id: int,
        spc: SurePetcareAPI,
        voltage_full: float,
        voltage_low: float,
    ):
        """Initialize a Sure Petcare battery sensor."""
        super().__init__(coordinator, _id, spc)

        self._attr_name = f"{self._attr_name} Battery Level"

        self.voltage_low = voltage_low
        self.voltage_full = voltage_full

        self._attr_unique_id = (
            f"{self._surepy_entity.household_id}-{self._surepy_entity.id}-battery"
        )

    @property
    def native_value(self) -> int | None:
        """Return battery level in percent."""

        if device := cast(SurepyDevice, self._data):
            return device.calculate_battery_level(
                voltage_full=self.voltage_full,
                voltage_low=self.voltage_low,
                num_batteries=NUM_BATTERIES,
            )

        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the additional attrs."""

        attrs: dict[str, Any] = {}

        if (device := cast(SurepyDevice, self._data)) and (
            state := device.raw_data().get("status")
        ):
            attrs = {**device.raw_data()}

            try:
                voltage = float(state["battery"])
            except (KeyError, TypeError, ValueError):
                return attrs

            attrs.update(
                {
                    ATTR_VOLTAGE: f"{voltage:.2f}",
                    f"{ATTR_VOLTAGE}_per_battery": f"{voltage / NUM_BATTERIES:.2f}",
                }
            )

        return attrs
