"""Support for Sure PetCare Flaps/Pets sensors."""

from __future__ import annotations

import logging
import pprint
from typing import Any, cast

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_VOLTAGE,
    UnitOfMass,
    PERCENTAGE,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from surepy.entities import SurepyEntity
from surepy.entities.devices import (
    Feeder as SureFeeder,
    FeederBowl as SureFeederBowl,
    Felaqua as SureFelaqua,
    Flap as SureFlap,
    SurepyDevice,
)
from surepy.enums import EntityType, LockState

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


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: Any,
    discovery_info: Any = None,
) -> None:
    """Set up Sure PetCare sensor platform."""
    await async_setup_entry(hass, config, async_add_entities)


async def async_setup_entry(
    hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: Any
) -> None:
    """Set up config entry Sure PetCare Flaps sensors."""

    entities: list[Flap | Felaqua | Feeder | FeederBowl | Battery] = []

    spc: SurePetcareAPI = hass.data[DOMAIN][config_entry.entry_id]

    for surepy_entity in spc.coordinator.data.values():

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
        ] and surepy_entity.raw_data().get("status", {}).get("locking"):
            entities.append(Flap(spc.coordinator, surepy_entity.id, spc))

        elif surepy_entity.type == EntityType.FELAQUA:
            entities.append(Felaqua(spc.coordinator, surepy_entity.id, spc))

        elif surepy_entity.type == EntityType.FEEDER:
            _LOGGER.debug(
                "DEBUG async_setup_entry: Setting up Feeder entity for %s (ID: %s)",
                surepy_entity.name,
                surepy_entity.id,
            )

            # --- Ensure FeederBowl entities are created from SureFeederBowl objects ---
            # This is the most reliable way to get bowl data
            if surepy_entity.bowls:
                _LOGGER.debug(
                    "DEBUG async_setup_entry: Found %d SureFeederBowl objects for Feeder ID %s. Creating FeederBowl sensors.",
                    len(surepy_entity.bowls),
                    surepy_entity.id,
                )
                for bowl_entity in surepy_entity.bowls.values():
                    entities.append(
                        FeederBowl(spc.coordinator, surepy_entity.id, spc, bowl_entity)
                    )
            else:
                _LOGGER.warning(
                    "WARNING async_setup_entry: No SureFeederBowl objects found in surepy_entity.bowls for Feeder ID: %s. Feeder bowl sensors will not be created.",
                    surepy_entity.id
                )
                # Removed any fallback to raw data to prevent unknown/duplicate sensors

            entities.append(Feeder(spc.coordinator, surepy_entity.id, spc))

        if surepy_entity.type in [
            EntityType.CAT_FLAP,
            EntityType.PET_FLAP,
            EntityType.FEEDER,
            EntityType.FELAQUA,
        ] and surepy_entity.raw_data().get("status", {}).get("battery") is not None:
            # Check if 'battery' key exists and is not None in raw_data().get("status")
            voltage_batteries_full = cast(
                float,
                config_entry.options.get(ATTR_VOLTAGE_FULL, SURE_BATT_VOLTAGE_FULL),
            )
            voltage_batteries_low = cast(
                float, config_entry.options.get(ATTR_VOLTAGE_LOW, SURE_BATT_VOLTAGE_LOW)
            )

            entities.append(
                Battery(
                    spc.coordinator,
                    surepy_entity.id,
                    spc,
                    voltage_full=voltage_batteries_full,
                    voltage_low=voltage_batteries_low,
                )
            )

    # Make sure this is set to True!
    async_add_entities(entities, True)


class SurePetcareSensor(CoordinatorEntity, SensorEntity):
    """A binary sensor implementation for Sure Petcare Entities."""

    _attr_should_poll = False

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI):
        """Initialize a Sure Petcare sensor."""
        super().__init__(coordinator)

        self._id = _id
        self._spc: SurePetcareAPI = spc

        self._coordinator = coordinator

        # Ensure that self._surepy_entity is correctly assigned from coordinator data
        # This will be the source of truth for all entity properties derived from surepy
        self._surepy_entity: SurepyEntity = self._coordinator.data[_id]
        
        # Initial status data for availability check and attributes.
        # It's important to use the latest status during coordinator updates.
        self._state: dict[str, Any] = self._surepy_entity.raw_data()["status"]

        self._attr_available = bool(self._state) # Basic availability based on status presence
        self._attr_unique_id = f"{self._surepy_entity.household_id}-{self._id}"

        # Initial extra_state_attributes; will be updated by extra_state_attributes property
        self._attr_extra_state_attributes = (
            {**self._surepy_entity.raw_data()} if self._state else {}
        )

        self._attr_name: str = (
            f"{self._surepy_entity.type.name.replace('_', ' ').title()} "
            f"{self._surepy_entity.name.capitalize()}"
        )

    @property
    def device_info(self):

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
                "name": self._surepy_entity.name.capitalize(),
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

        except AttributeError:
            pass

        return device


class Flap(SurePetcareSensor):
    """Sure Petcare Flap."""

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI) -> None:
        super().__init__(coordinator, _id, spc)

        self._surepy_entity = cast(SureFlap, self._surepy_entity) # Type hint for specific entity type

        self._attr_entity_picture = self._surepy_entity.icon
        self._attr_unit_of_measurement = None

        if self._state:
            self._attr_extra_state_attributes = {
                "learn_mode": bool(self._state["learn_mode"]),
                **self._surepy_entity.raw_data(),
            }
            # Set initial state if available
            if locking := self._state.get("locking"):
                self._attr_state = LockState(locking["mode"]).name.casefold()

    @property
    def state(self) -> str | None:
        """Return lock state."""
        # Get the latest data from the coordinator
        current_entity = cast(SureFlap, self._coordinator.data.get(self._id))
        if current_entity and (state := current_entity.raw_data().get("status")):
            return LockState(state["locking"]["mode"]).name.casefold()
        return None


class Felaqua(SurePetcareSensor):
    """Sure Petcare Felaqua."""

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI):
        super().__init__(coordinator, _id, spc)

        self._surepy_entity = cast(SureFelaqua, self._surepy_entity) # Type hint for specific entity type

        self._attr_entity_picture = self._surepy_entity.icon
        self._attr_unit_of_measurement = UnitOfVolume.MILLILITERS

    @property
    def state(self) -> float | None:
        """Return the remaining water."""
        # Get the latest data from the coordinator
        current_entity = cast(SureFelaqua, self._coordinator.data.get(self._id))
        if current_entity:
            return int(current_entity.water_remaining) if current_entity.water_remaining is not None else None
        return None


class FeederBowl(SurePetcareSensor):
    """Sure Petcare Feeder Bowl."""

    def __init__(
        self,
        coordinator,
        _id: int,
        spc: SurePetcareAPI,
        bowl_entity: SureFeederBowl, # <--- Now strictly SureFeederBowl
    ):
        """Initialize a Bowl sensor."""
        super().__init__(coordinator, _id, spc)

        _LOGGER.debug("DEBUG FeederBowl __init__: Received SureFeederBowl object: %s", pprint.pformat(bowl_entity.raw_data()))

        self.feeder_id = _id
        self._bowl_entity: SureFeederBowl = bowl_entity # Store the actual SureFeederBowl object

        self.bowl_id = self._bowl_entity.id # Use the stable ID from the SureFeederBowl object
        self._bowl_index = self._bowl_entity.index # This is also stable (e.g., 0 or 1 for dual bowls)

        self._spc: SurePetcareAPI = spc

        self._surepy_feeder_entity: SurepyEntity = self._coordinator.data[_id]

        # Use index for naming. Add 1 for user-friendly 1-based indexing if preferred.
        self._attr_name = (
            f"{EntityType.FEEDER.name.replace('_', ' ').title()} "
            f"{self._surepy_feeder_entity.name.capitalize()} Bowl {self._bowl_entity.index + 1}"
        )

        self._attr_icon = "mdi:bowl"
        self._attr_unit_of_measurement = UnitOfMass.GRAMS

        # Unique ID using the stable bowl_id from SureFeederBowl object
        self._attr_unique_id = (
            f"{self._surepy_feeder_entity.household_id}-{self.feeder_id}-bowl-{self.bowl_id}"
        )
        _LOGGER.debug(
            "DEBUG FeederBowl __init__: Initialized FeederBowl entity for Feeder ID: %s, Bowl ID: %s, Unique ID: %s, Name: %s",
            self.feeder_id,
            self.bowl_id,
            self._attr_unique_id,
            self._attr_name
        )

    @property
    def state(self) -> float | None:
        """Return the remaining food in the bowl."""
        _LOGGER.debug(f"DEBUG FeederBowl.state: Attempting to get state for Bowl ID: {self.bowl_id} (Unique ID: {self._attr_unique_id})")
        
        # Get the latest feeder data from the coordinator
        feeder = cast(SureFeeder, self._coordinator.data.get(self.feeder_id))
        
        if feeder and self.bowl_id in feeder.bowls:
            bowl = feeder.bowls[self.bowl_id]
            if bowl.weight is not None:
                _LOGGER.debug(f"DEBUG FeederBowl.state: Found bowl weight for ID {self.bowl_id}: {bowl.weight}")
                return int(bowl.weight)
            else:
                _LOGGER.debug(f"DEBUG FeederBowl.state: Bowl weight is None for ID {self.bowl_id}. Returning None.")
        else:
            _LOGGER.debug(f"DEBUG FeederBowl.state: Bowl ID {self.bowl_id} not found in feeder.bowls or feeder is None. Returning None.")
        
        return None


class Feeder(SurePetcareSensor):
    """Sure Petcare Feeder."""

    def __init__(self, coordinator, _id: int, spc: SurePetcareAPI):
        """Initialize a Feeder sensor."""
        super().__init__(coordinator, _id, spc)

        self._surepy_entity = cast(SureFeeder, self._surepy_entity) # Type hint for specific entity type

        self._attr_entity_picture = self._surepy_entity.icon
        self._attr_unit_of_measurement = UnitOfMass.GRAMS

        # Add or modify unique_id explicitly for Feeder to be highly distinct
        self._attr_unique_id = (
            f"{self._surepy_entity.household_id}-{self._id}-total_food"
        )

        # Add this debug log for initial state/entity details
        _LOGGER.debug(
            "DEBUG Feeder __init__: Initializing Feeder entity for ID: %s, Name: %s, Unique ID: %s. Raw Data Status: %s",
            self._id,
            self._surepy_entity.name,
            self._attr_unique_id,  # Log the unique ID too
            pprint.pformat(self._surepy_entity.raw_data().get("status", "Status key not found in raw_data")),
        )

    @property
    def state(self) -> float | None:
        """Return the total remaining food."""
        _LOGGER.debug(
            "DEBUG Feeder.state: Attempting to get state for entity ID: %s (Unique ID: %s)",
            self._id,
            self._attr_unique_id,
        )

        # Use .get() for safer access to avoid KeyError if _id isn't in data
        feeder = cast(SureFeeder, self._coordinator.data.get(self._id))

        if feeder:
            _LOGGER.debug(
                "DEBUG Feeder.state: Feeder data found for ID %s. total_weight: %s (Type: %s). Raw data (status key): %s",
                self._id,
                feeder.total_weight,
                type(feeder.total_weight),
                pprint.pformat(feeder.raw_data().get("status", "Status key not found in raw_data")),
            )

            if feeder.total_weight is not None:
                try:
                    return int(feeder.total_weight)  # Return the actual integer value, even if it's 0
                except (ValueError, TypeError) as e:
                    _LOGGER.error(
                        "ERROR Feeder.state: Could not convert total_weight '%s' (type %s) to int for entity ID %s. Error: %s",
                        feeder.total_weight,
                        type(feeder.total_weight),
                        self._id,
                        e
                    )
                    return None  # If conversion fails, then it's truly unavailable
            else:
                _LOGGER.debug(
                    "DEBUG Feeder.state: total_weight is None for entity ID: %s", self._id
                )
                return None  # If total_weight is None from the API, then the sensor is truly unavailable
        else:
            _LOGGER.debug(
                "DEBUG Feeder.state: No feeder data found in coordinator.data for entity ID: %s. Entity might be unavailable.", self._id
            )
            return None


class Battery(SurePetcareSensor):
    """Sure Petcare Battery Sensor."""

    def __init__(
        self,
        coordinator,
        _id: int,
        spc: SurePetcareAPI,
        voltage_full: float,
        voltage_low: float,
    ):
        super().__init__(coordinator, _id, spc)

        self._surepy_entity = cast(SurepyDevice, self._surepy_entity) # Type hint for specific entity type

        # Set these attributes in __init__
        self._attr_name = f"{self._attr_name} Battery Level"
        self._attr_unit_of_measurement = PERCENTAGE
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_unique_id = (
            f"{self._surepy_entity.household_id}-{self._surepy_entity.id}-battery"
        )

        self.voltage_low = voltage_low
        self.voltage_full = voltage_full

        # Add debug log for Battery __init__
        _LOGGER.debug(
            "DEBUG Battery __init__: Initializing Battery entity for ID: %s, Name: %s, Unique ID: %s. Voltage Full: %s, Voltage Low: %s. Raw Data Status: %s",
            self._id,
            self._attr_name,
            self._attr_unique_id,
            self.voltage_full,
            self.voltage_low,
            pprint.pformat(self._surepy_entity.raw_data().get("status", "Status key not found in raw_data")),
        )


    @property
    def state(self) -> int | None:
        """Return battery level in percent."""
        _LOGGER.debug(f"DEBUG Battery.state: Attempting to get state for battery ID: {self._id} (Unique ID: {self._attr_unique_id})")

        # Get the latest device data from the coordinator
        device_data = self._coordinator.data.get(self._id)
        if not device_data:
            _LOGGER.debug(f"DEBUG Battery.state: No device data found in coordinator for ID: {self._id}. Sensor likely unavailable.")
            return None # Sensor is truly unavailable if no device data in coordinator

        # Ensure we are working with a SurepyDevice type for its methods
        battery_device = cast(SurepyDevice, device_data)
        
        # Log the raw status data from the device to confirm voltage presence
        raw_status = battery_device.raw_data().get("status")
        if raw_status:
            _LOGGER.debug(f"DEBUG Battery.state: Device ID {self._id} raw status: {pprint.pformat(raw_status)}")
        else:
            _LOGGER.debug(f"DEBUG Battery.state: Device ID {self._id} has no 'status' key in raw_data. Cannot determine battery level.")
            return None # If no status, cannot get battery level

        # Call calculate_battery_level from the SurepyDevice object
        battery_level = battery_device.calculate_battery_level(
            voltage_full=self.voltage_full,
            voltage_low=self.voltage_low
        )

        _LOGGER.debug(
            f"DEBUG Battery.state: Device ID {self._id} (Name: {self._attr_name}): "
            f"Calculated battery level: {battery_level} "
            f"using voltage_full={self.voltage_full}, voltage_low={self.voltage_low}."
        )

        # Surepy's calculate_battery_level returns an int or None
        if battery_level is not None:
            # Ensure the level is within expected bounds (0-100)
            return max(0, min(100, battery_level))
        
        _LOGGER.warning(f"WARNING Battery.state: battery_level is None for device ID {self._id}. This means Surepy's calculate_battery_level returned None.")
        return None


    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the additional attrs."""

        attrs = {}

        # Get the latest device data from the coordinator.
        # This ensures attributes reflect current state, not just __init__ state.
        device_data = self._coordinator.data.get(self._id)

        if (device_data) and (
            state := device_data.raw_data().get("status")
        ):
            # Use .get() with a default value to prevent KeyError if 'battery' is missing
            voltage = float(state.get("battery", 0.0)) 

            attrs = {
                # Use battery_device.battery_level property from surepy for consistency
                "battery_level_from_surepy": device_data.battery_level, 
                ATTR_VOLTAGE: f"{voltage:.2f}",
                # Only show per_battery if voltage is non-zero to avoid division by zero
                f"{ATTR_VOLTAGE}_per_battery": f"{voltage / 4:.2f}" if voltage else "0.00", 
            }
        
        _LOGGER.debug(f"DEBUG Battery.extra_state_attributes: For ID {self._id}, attributes: {attrs}")

        return attrs
