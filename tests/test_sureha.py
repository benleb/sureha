"""Smoke tests for the SureHA custom integration."""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_TOKEN, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from surepy.entities.devices import Feeder, Felaqua, Flap, Hub
from surepy.entities.pet import Pet
from surepy.exceptions import SurePetcareAuthenticationError, SurePetcareError

from custom_components.sureha.const import DOMAIN

HH = 999
SINCE = (datetime.now(timezone.utc) - timedelta(days=1, hours=2, minutes=5)).strftime(
    "%Y-%m-%dT%H:%M:%S+00:00"
)


def entities():
    return {
        1: Hub({"id": 1, "product_id": 1, "household_id": HH, "name": "hub",
                "status": {"led_mode": 4, "pairing_mode": 0, "online": True}}),
        2: Flap({"id": 2, "product_id": 6, "household_id": HH, "name": "flap",
                 "status": {"locking": {"mode": 1}, "battery": 5.6, "learn_mode": False,
                            "online": True, "signal": {"device_rssi": -50, "hub_rssi": -60}}}),
        3: Feeder({"id": 3, "product_id": 4, "household_id": HH, "name": "feeder",
                   "control": {"bowls": {"settings": [{"food_type": 1}, {"food_type": 1}]}},
                   "lunch": {"weights": [{"index": 0, "weight": 20.5, "change": -3},
                                         {"index": 1, "weight": 0, "change": 0}]},
                   "status": {"battery": 5.2, "online": True}}),
        4: Felaqua({"id": 4, "product_id": 8, "household_id": HH, "name": "water",
                    "latest_drink": {"remaining": 0},
                    "status": {"battery": 5.0, "online": True}}),
        10: Pet({"id": 10, "household_id": HH, "name": "Thorin",
                 "position": {"where": 1, "since": SINCE}}),
        11: Pet({"id": 11, "household_id": HH, "name": "Nopos"}),  # no position
    }


def make_surepy():
    surepy = MagicMock()
    surepy.get_entities = AsyncMock(side_effect=lambda refresh=False: entities())
    surepy.sac = MagicMock()
    for m in ("lock", "lock_in", "lock_out", "unlock", "set_pet_location"):
        setattr(surepy.sac, m, AsyncMock(return_value={}))
    return surepy


async def test_config_flow(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] == FlowResultType.FORM

    data = {CONF_USERNAME: "User@x.it", CONF_PASSWORD: "pw"}

    with patch("custom_components.sureha.config_flow.Surepy") as sp:
        sp.return_value.sac.get_token = AsyncMock(side_effect=SurePetcareAuthenticationError("x"))
        r = await hass.config_entries.flow.async_configure(result["flow_id"], data)
        assert r["type"] == FlowResultType.FORM and r["errors"] == {"base": "invalid_auth"}

        sp.return_value.sac.get_token = AsyncMock(side_effect=SurePetcareError("x"))
        r = await hass.config_entries.flow.async_configure(result["flow_id"], data)
        assert r["errors"] == {"base": "cannot_connect"}

        sp.return_value.sac.get_token = AsyncMock(return_value="tok")
        with patch("custom_components.sureha.async_setup_entry", return_value=True):
            r = await hass.config_entries.flow.async_configure(result["flow_id"], data)
        assert r["type"] == FlowResultType.CREATE_ENTRY
        assert r["data"][CONF_TOKEN] == "tok"

    # duplicate
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_USERNAME: "user@X.it", CONF_PASSWORD: "pw"})
    assert r["type"] == FlowResultType.ABORT and r["reason"] == "already_configured"


async def setup(hass):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="u",
                            data={CONF_USERNAME: "u", CONF_PASSWORD: "p", CONF_TOKEN: "t"})
    entry.add_to_hass(hass)
    surepy = make_surepy()
    with patch("custom_components.sureha.Surepy", return_value=surepy):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry, surepy


async def test_setup_services_unload(hass):
    entry, surepy = await setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    states = {s.entity_id: s for s in hass.states.async_all()}
    for eid, s in sorted(states.items()):
        print(eid, s.state, {k: v for k, v in s.attributes.items() if k in ("for", "unit_of_measurement", "voltage")})

    flap = [s for e, s in states.items() if e.startswith("sensor.") and "flap" in e and "battery" not in e][0]
    assert flap.state == "locked_in"
    bowls = sorted(s.state for e, s in states.items() if "bowl" in e)
    assert bowls == ["0", "20"], bowls
    water = [s for e, s in states.items() if e.startswith("sensor.felaqua")][0]
    assert water.state == "0"
    batt = [s for e, s in states.items() if "flap" in e and "battery" in e][0]
    assert batt.state == "42" and batt.attributes["voltage"] == "5.60"
    pet = [s for e, s in states.items() if e.startswith("binary_sensor.") and "thorin" in e][0]
    assert pet.state == "on" and pet.attributes["for"].startswith("1d 02:0")
    nopos = [s for e, s in states.items() if e.startswith("binary_sensor.") and "nopos" in e][0]
    assert "for" not in nopos.attributes and nopos.state == "off"
    tracker = [s for e, s in states.items() if e.startswith("device_tracker.") and "nopos" in e][0]
    assert tracker.state == "not_home"

    await hass.services.async_call(DOMAIN, "set_lock_state", {"flap_id": "2", "lock_state": " Locked_All "}, blocking=True)
    surepy.sac.lock.assert_awaited_once_with(2)
    await hass.services.async_call(DOMAIN, "set_pet_location", {"pet_id": "10", "where": "outside"}, blocking=True)
    assert surepy.sac.set_pet_location.await_args.args[0] == 10
    with pytest.raises(Exception):
        await hass.services.async_call(DOMAIN, "set_pet_location", {"pet_id": 10, "where": "garden"}, blocking=True)
    with pytest.raises(Exception):
        await hass.services.async_call(DOMAIN, "set_lock_state", {"flap_id": 2, "lock_state": "locked"}, blocking=True)
    surepy.sac.unlock.side_effect = SurePetcareError("boom")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(DOMAIN, "set_lock_state", {"flap_id": 2, "lock_state": "unlocked"}, blocking=True)

    # options flow + reload
    r = await hass.config_entries.options.async_init(entry.entry_id)
    assert r["type"] == FlowResultType.FORM
    r2 = await hass.config_entries.options.async_configure(r["flow_id"], {"voltage_low": 1.6, "voltage_full": 1.2})
    assert r2["errors"] == {"base": "invalid_voltage"}
    with patch("custom_components.sureha.Surepy", return_value=surepy):
        r2 = await hass.config_entries.options.async_configure(r["flow_id"], {"voltage_low": 1.2, "voltage_full": 1.5})
        assert r2["type"] == FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.services.has_service(DOMAIN, "set_lock_state")


async def test_remove_pet_device(hass, hass_ws_client):
    """A pet still reported by Sure Petcare can be deleted and stays away."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from homeassistant.setup import async_setup_component

    assert await async_setup_component(hass, "config", {})
    entry, surepy = await setup(hass)
    dev_reg, ent_reg = dr.async_get(hass), er.async_get(hass)

    def pet_entities():
        return sorted(e.entity_id for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id) if "thorin" in e.entity_id)

    assert pet_entities() == ["binary_sensor.pet_thorin", "device_tracker.pet_thorin"]
    device = dev_reg.async_get_device(identifiers={(DOMAIN, 10)})
    assert device is not None

    client = await hass_ws_client(hass)
    with patch("custom_components.sureha.Surepy", return_value=surepy):
        await client.send_json_auto_id(
            {"type": "config/device_registry/remove_config_entry",
             "config_entry_id": entry.entry_id, "device_id": device.id}
        )
        response = await client.receive_json()
        assert response["success"], response
        await hass.async_block_till_done()

    assert entry.options["ignored_ids"] == [10]
    assert entry.state is ConfigEntryState.LOADED
    assert dev_reg.async_get_device(identifiers={(DOMAIN, 10)}) is None
    assert pet_entities() == []
    assert hass.states.get("binary_sensor.pet_thorin") is None
    # the other pet and the devices are untouched
    assert hass.states.get("binary_sensor.pet_nopos") is not None
    assert hass.states.get("sensor.cat_flap_flap") is not None

    # it can be restored from the options
    r = await hass.config_entries.options.async_init(entry.entry_id)
    assert r["type"] == FlowResultType.FORM
    with patch("custom_components.sureha.Surepy", return_value=surepy):
        r = await hass.config_entries.options.async_configure(
            r["flow_id"], {"voltage_low": 1.25, "voltage_full": 1.6, "ignored_ids": []}
        )
        assert r["type"] == FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
    assert entry.options["ignored_ids"] == []
    assert hass.states.get("binary_sensor.pet_thorin") is not None


async def test_pet_removed_from_account(hass):
    """Pets that left the Sure Petcare account are cleaned up automatically."""
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    from surepy.const import MESTART_RESOURCE

    entry = MockConfigEntry(domain=DOMAIN, unique_id="u",
                            data={CONF_USERNAME: "u", CONF_PASSWORD: "p", CONF_TOKEN: "t"})
    entry.add_to_hass(hass)
    dev_reg, ent_reg = dr.async_get(hass), er.async_get(hass)

    # leftovers of a pet removed while Home Assistant was not running
    old = dev_reg.async_get_or_create(config_entry_id=entry.entry_id, identifiers={(DOMAIN, 31337)}, name="Old")
    ent_reg.async_get_or_create("binary_sensor", DOMAIN, f"{HH}-31337", config_entry=entry, device_id=old.id)
    ent_reg.async_get_or_create("device_tracker", DOMAIN, "31337_pet_tracker", config_entry=entry)

    account = {"devices": [{"id": i} for i in (1, 2, 3, 4)], "pets": [{"id": 10}, {"id": 11}]}
    surepy = make_surepy()
    surepy.entities = {}
    surepy.sac.resources = {MESTART_RESOURCE: {"data": account}}

    async def get_entities(refresh=False):
        # like surepy: entities seen once are returned forever
        ids = {i["id"] for i in account["devices"] + account["pets"]}
        surepy.entities.update({k: v for k, v in entities().items() if k in ids})
        return surepy.entities

    surepy.get_entities = AsyncMock(side_effect=get_entities)

    with patch("custom_components.sureha.Surepy", return_value=surepy):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        assert dev_reg.async_get(old.id) is None
        assert not [e for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id) if "31337" in e.unique_id]
        assert hass.states.get("binary_sensor.pet_thorin") is not None
        assert hass.states.get("device_tracker.pet_thorin") is not None

        # the pet is deleted in the Sure Petcare app while HA is running
        account["pets"] = [{"id": 11}]
        await hass.data[DOMAIN]["spc"].coordinator.async_refresh()
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("binary_sensor.pet_thorin") is None
    assert hass.states.get("device_tracker.pet_thorin") is None
    assert dev_reg.async_get_device(identifiers={(DOMAIN, 10)}) is None
    assert not [e for e in er.async_entries_for_config_entry(ent_reg, entry.entry_id) if "thorin" in e.entity_id]
    assert hass.states.get("binary_sensor.pet_nopos") is not None
    assert hass.states.get("sensor.cat_flap_flap") is not None


async def test_flap_locks(hass):
    """Lock entities behave like the official integration."""
    from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
    from homeassistant.const import ATTR_ENTITY_ID

    flap_mode = {"mode": 1}  # locked_in
    surepy = make_surepy()

    def current_entities(refresh=False):
        data = entities()
        data[2].raw_data()["status"]["locking"]["mode"] = flap_mode["mode"]
        return data

    surepy.get_entities = AsyncMock(side_effect=current_entities)

    def api(mode):
        async def call(flap_id):
            assert flap_id == 2
            flap_mode["mode"] = mode
        return call

    surepy.sac.unlock = AsyncMock(side_effect=api(0))
    surepy.sac.lock_in = AsyncMock(side_effect=api(1))
    surepy.sac.lock_out = AsyncMock(side_effect=api(2))
    surepy.sac.lock = AsyncMock(side_effect=api(3))

    entry = MockConfigEntry(domain=DOMAIN, unique_id="u",
                            data={CONF_USERNAME: "u", CONF_PASSWORD: "p", CONF_TOKEN: "t"})
    entry.add_to_hass(hass)
    with patch("custom_components.sureha.Surepy", return_value=surepy):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    ids = {m: f"lock.flap_{m}" for m in ("locked_in", "locked_out", "locked_all")}

    def states():
        return {m: hass.states.get(e).state for m, e in ids.items()}

    assert states() == {"locked_in": "locked", "locked_out": "unlocked", "locked_all": "unlocked"}
    # the locks belong to the flap device
    from homeassistant.helpers import device_registry as dr, entity_registry as er
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, 2)})
    assert er.async_get(hass).async_get(ids["locked_all"]).device_id == device.id

    async def call(service, mode):
        await hass.services.async_call(LOCK_DOMAIN, service, {ATTR_ENTITY_ID: ids[mode]}, blocking=True)
        await hass.async_block_till_done()

    # locking another mode switches the flap; all three entities follow at once
    await call("lock", "locked_all")
    surepy.sac.lock.assert_awaited_once_with(2)
    assert states() == {"locked_in": "unlocked", "locked_out": "unlocked", "locked_all": "locked"}

    # unlocking a mode that is not active does nothing
    await call("unlock", "locked_out")
    surepy.sac.unlock.assert_not_awaited()

    # unlocking the active mode unlocks the flap
    await call("unlock", "locked_all")
    surepy.sac.unlock.assert_awaited_once_with(2)
    assert set(states().values()) == {"unlocked"}
    assert hass.states.get("sensor.cat_flap_flap").state == "unlocked"

    # API errors are reported and the state is unchanged
    surepy.sac.lock_out.side_effect = SurePetcareError("boom")
    with pytest.raises(HomeAssistantError):
        await call("lock", "locked_out")
    assert set(states().values()) == {"unlocked"}
