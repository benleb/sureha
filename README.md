# SureHA 🐾

> **Note:** This is a modified, enhanced, and actively maintained fork of the original SureHA integration. 

## ✨ New Features in this Fork
* **Smart Duration Tracking:** The pet location sensor now includes a `for` attribute (e.g., `1d 04:30` or `02:15`), calculating exactly how long your pet has been inside or outside. No more need for complex Jinja2 templates!
* **Enhanced Battery & Connectivity Stats:** Added exact voltage per cell and formatted RSSI signal strengths for easier debugging of hub connections.

---

## Entities

This project creates the following entities in your Home Assistant instance:

### `sensor.cat_flap`

There will be 1 entity per cat flap with the following attributes:
<details>
  <summary>Click to expand!</summary>
  
  *This is a non-exhaustive list*
  
| Attribute | Example |
|---------------------|-------------------|  
| ID                  | 123456                                                                                                    |
| Parent device ID    | 123456                                                                                                    |
| Product ID          | 6                                                                                                         |
| Household ID        | 123456                                                                                                    |
| Name                | Rivendell                                                                                                 |
| Serial number       | XXXX-XXXXX                                                                                                |
| MAC address         | 2c549188c9e3                                                                                              |
| Index               | 0                                                                                                         |
| Version             | ODM2                                                                                                      |
| Created at          | December 19, 2024, 1:43:25 AM                                                                             |
| Updated at          | December 19, 2024, 1:43:25 AM                                                                             |
| Pairing at          | December 19, 2024, 1:43:25 AM                                                                             |
| Control             | curfew: <br>- enabled:true<br> lock_time:"22:00"<br> unlock_time: "07:30"<br> locking: 0<br> fast_polling:false |
| Parent              | |
| Status              | locking:<br> mode: 0 <br>version:<br> battery: 5.07<br> learn_mode:<br> online:true                       |
| Tags                | |
</details>

### `sensor.cat_flap_battery`

<details>
  <summary>Click to expand!</summary>
  
The state is the battery level in % (calculated with the voltages set in the integration options).

| Attribute | Example |
|---------------------|-------------------|
| Voltage             | 5.09              |
| Voltage per battery | 1.27              |
</details>

### `binary_sensor.flap_connectivity` / `binary_sensor.hub`

<details>
  <summary>Click to expand!</summary>

| Attribute   | Example |
|-------------|---------|
| Device rssi | -35.00  |
| Hub rssi    | -42.00  |

</details>

### `binary_sensor.pet`

<details>
  <summary>Click to expand!</summary>

| Attribute                  | Example                                                                |
|----------------------------|------------------------------------------------------------------------|
| **For (Duration)**         | **04:25** or **1d 04:25** (time since last move; omitted if unknown)   |
| Since                      | September 18, 2024, 4:09:42 PM                                         |
| Where                      | 1 (Inside) / 2 (Outside)                                               |
| ID                         | 123456                                                                 |
| Name                       | Thorin                                                                 |
| Gender                     | 1                                                                      |
| Comments                   | Such a good cute boy                                                   |
| Household ID               | 123456                                                                 |
| Breed ID                   | 384                                                                    |
| Photo ID                   | 123456                                                                 |
| Version                    | Mg==                                                                   |
| Created at                 | April 1, 2024, 11:00:07 AM                                             |
| Photo                      | id: 238217  <br> location https://surehub.s3.amazonaws.com/...         |
| Status                     | activity:<br> tag_id: 123456 <br>where: 1 <br>since: date              |

</details>


## Removing a pet or device

If a pet or device is still listed in your Sure Petcare account but you no longer want it in Home Assistant:

1. Go to **Settings → Devices & services → SureHA** and open the pet/device.
2. Use the **⋮ menu → Delete**.

Its entities are removed and it is added to the *ignored* list, so it is not created again.
To bring it back, open the integration's **Configure** dialog and untick it under *Ignored pets/devices*.

## Services

This project allows you to use the following services in Home Assistant:<br>

### `sureha.set_pet_location`
 
 This service call allows you to update the location of a pet manually. <br>
 Data needed:<br>
   - `pet_id` = this is the surepetcare id for your pet. <br>
   - `where` = options are "Inside" or "Outside"

Example:
```yaml
service: sureha.set_pet_location
data:
  pet_id: 31337
  where: Inside
```

### `sureha.set_lock_state`

 This service call allows you to update the lock state of a flap.
  
 Data needed:<br>
   - `flap_id` = this is the surepetcare id for the flap you want to change.<br>
   - `lock_state` = one of:
     - `unlocked` – pets can go in and out
     - `locked_in` – pets can come in but not go out
     - `locked_out` – pets can go out but not come in
     - `locked_all` – flap locked in both directions

 Example:
```yaml
service: sureha.set_lock_state
data:
  flap_id: 123456
  lock_state: locked_all
```


## Useful stuff

The following script and button card code was created by xbmcnut to set pets location to inside:
```yaml
script:
  set_kobe_inside:
    alias: 'Set Kobe Inside'
    sequence:
      - service: sureha.set_pet_location
        data:
          pet_id: '123456' #Kobe's Code
          where: Inside      
```

Button card code:
```yaml
type: custom:button-card
entity: binary_sensor.pet_kobe
icon: mdi:cat
layout: icon_name_state
show_name: false
show_state: true
styles:
  icon:
    - color: >
        [[[ if (states['binary_sensor.pet_kobe'].state === 'on') return "green";
        return "red"; ]]]
tap_action:
  action: more-info
hold_action:
  action: call-service
  service: script.set_kobe_inside
```

The following script was created by sasgoose to toggle the location of a pet:

```yaml
script:
  toggle_thorin_location:
      alias: 'Toggle Thorin location'
      sequence:
        choose:
        - conditions:
            - condition: state
              entity_id: binary_sensor.pet_thorin_2
              attribute: where
              state: 1
          sequence:
            - service: sureha.set_pet_location
              data:
                pet_id: '123456' # Thorin's pet id
                where: Outside
        - conditions:
            - condition: state
              entity_id: binary_sensor.pet_thorin_2
              attribute: where
              state: 2
          sequence:
            - service: sureha.set_pet_location
              data:
                pet_id: '123456' # Thorin's pet id
                where: Inside
                
```

## Debugging

Enable the debug logging in `configuration.yaml` if something does not work as expected:

```yaml
# logging
logger:
  default: info
  logs:
    surepy: debug
    custom_components.sureha: debug
    custom_components.sureha.binary_sensor: debug
    custom_components.sureha.sensor: debug
```

---

## Credits & Acknowledgements 🐾

This repository is maintained at **[scoprire87/sureha](https://github.com/scoprire87/sureha)**.

Huge thanks to **Ben Ervin (benleb)** for the original `surepy` library and the initial development of the custom integration that made this possible.

| Name | Developer | Description |
|---|---|---|
| **[SureHA](https://github.com/scoprire87/sureha)** | [@scoprire87](https://github.com/scoprire87) | This Custom Home Assistant Integration. |
| **[surepy](https://github.com/benleb/surepy)** | [@benleb](https://github.com/benleb) | Python Library to interact with the API of Sure Petcare. |
| **[Official HA Integration](https://www.home-assistant.io/integrations/surepetcare)** | Home Assistant Core | Official (but limited) Home Assistant Integration. |
