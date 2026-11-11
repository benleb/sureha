# SureHA 🐾

> documentation is currently in a bad state. I am aware of this and working on it!

## Entities

This project creates the following entities in your Home Assistant instance:<br>

### sensor.cat_flap

There will be 1 entity per cat flap with the following attributes
<details>
  <summary>Click to expand!</summary>
  
  This is a non-exhaustive list
  
| Attribute | Example |
|---------------------|-------------------|  
| ID               | 123456                                                                                      |
| Parent device ID | 123456                                                                                      |
| Product ID       | 6                                                                                           |
| Household ID     | 123456                                                                                      |
| Name             | Rivendell                                                                                   |
| Serial number    | XXXX-XXXXX                                                                                  |
| MAC address      | 2c549188c9e3                                                                                |
| Index            | 0                                                                                           |
| Version          | ODM2                                                                                        |
| Created at       | December 19, 2018, 1:43:25 AM                                                               |
| Updated at       | December 19, 2018, 1:43:25 AM                                                               |
| Pairing at       | December 19, 2018, 1:43:25 AM                                                               |
| Control          | curfew: <br>- enabled:true<br> lock_time:"22:00"<br> unlock_time: "07:30"<br> locking: 0<br> fast_polling:false |
| Parent           | |
| Status           | locking:<br> mode: 0 <br>version:<br> battery: 5.07<br> learn_mode:<br> online:true                             |
| Tags | |
| Move | |
</details>

### sensor.cat_flap_battery

<details>
  <summary>Click to expand!</summary>
  
| Attribute | Example |
|---------------------|-------------------|
The state is the battery level in % (calculated with the voltages set in the integration options).

| Attribute | Example |
|---------------------|-------------------|
| Voltage             | 5.09              |
| Voltage per battery | 1.27              |
</details>

### lock.\<flap\>_locked_in / lock.\<flap\>_locked_out / lock.\<flap\>_locked_all

Every cat/pet flap gets three lock entities, like the official Sure Petcare integration:

| Entity | Locked means |
|---|---|
| `lock.<flap>_locked_in` | pets can come in but not go out |
| `lock.<flap>_locked_out` | pets can go out but not come in |
| `lock.<flap>_locked_all` | the flap is locked in both directions |

Locking one of them switches the flap to that mode (the other two become unlocked).
Unlocking the active one unlocks the flap; unlocking a mode that is not active does nothing.
During a curfew all three are shown as unlocked.

### binary_sensor.hub

<details>
  <summary>Click to expand!</summary>

| Attribute   | Example |
|-------------|---------|
| Device rssi | -35.00  |
| Hub rssi    | -35.00  |

</details>

### binary_sensor.pet

<details>
  <summary>Click to expand!</summary>

| Attribute                  | Example                                                                |
|----------------------------|------------------------------------------------------------------------|
| For                        | 04:25 or 1d 04:25 (time since the last move; omitted if unknown)       |
| Since                      | September 18, 2021, 4:09:42 PM                                         |
| Where                      | 1                                                                      |
| ID                         | 123456                                                                 |
| Name                       | Thorin                                                                 |
| Gender                     | 1                                                                      |
| Comments                   | Such a good cute boy                                                   |
| Household ID               | 123456                                                                 |
| Breed ID                   | 384                                                                    |
| Photo ID                   | 123456                                                                 |
| Species ID                 |                                                                        |
| Tag ID                     | 123456                                                                 |
| Version                    | Mg==                                                                   |
| Created at                 | April 1, 2021, 11:00:07 AM                                             |
| Updated at                 | April 1, 2021, 11:00:07 AM                                             |
| April 2, 2021, 10:20:49 PM |                                                                        |
| Photo                      | id: 238217  <br> location https://surehub.s3.amazonaws.com/user-photos/thm/imageURL.jpg |
| Position                   | tag_id: 1233456 <br> user_id: 123456 <br>where: 1<br> since: date                   |
| Status                     | activity:<br> tag_id: 123456 <br>user_id: 123456<br> where: 1 <br>since: date          |

</details>

### binary_sensor.flap_connectivity

`on` when the device (flap, feeder, Felaqua) is online.

<details>
  <summary>Click to expand!</summary>

| Attribute   | Example |
|-------------|---------|
| Device rssi | -35.00  |
| Hub rssi    | -42.00  |

</details>

## Removing a pet or device

Pets and devices that are removed from your Sure Petcare account are removed from Home Assistant automatically (within a few minutes, or at the next restart).

If a pet or device is still listed in your Sure Petcare account but you no longer want it in Home Assistant:

1. Go to **Settings → Devices & services → SureHA** and open the pet/device.
2. Use the **⋮ menu → Delete**.

Its entities are removed and it is added to the *ignored* list, so it is not created again.
To bring it back, open the integration's **Configure** dialog and untick it under *Ignored pets/devices*.

## Services

This project allows you to use the following services in Home Assistant:<br>

### SureHA: Set Pet location<br>
 
  This service call allows you to update the location of a pet. <br>
  Data needed:<br>
    - pet_id = this is the surepetcare id for your pet. <br>
    - where = options are "Inside" or "Outside"

example:
```yaml
service: sureha.set_pet_location
data:
  pet_id: 31337
  where: Inside
```

### SureHA: Set lock state

  This service call allows you to update the lock state of a flap.
  
  Data needed:<br>
    - flap_id = this is the surepetcare id for the flap you want to change.<br>
    - lock_state = one of `unlocked`, `locked_in`, `locked_out`, `locked_all`
  
example:
```yaml
service: sureha.set_lock_state
data:
  flap_id: 123456
  lock_state: locked_all
```


## Useful stuff

The following script and button card code was create by xbmcnut to set pets location to inside
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
type: custom:button-card
```

The following script was created by sasgoose to toggle the location of a pet

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


## Upgrade *surepetcarebeta* to *sureha*

Do a backup of your HA first. Its probably not needed but a backup is never a bad idea ;)  
The cleanest way will be to delete the *surepetcarebeta* integration completely and handle *sureha* completely independent. It will create the same entity/unique ids as before so your automations and graphs should not be affected.

## enable the debug logging in `configuration.yaml` if something does not work as expected

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

## Naming confusion for *surepetcarebeta* users 🐾 🤪 🤦

Sorry for the bad naming and resulting confusion and chaos 🙄 To "fix" this, I **renamed *surepetcarebeta* to *sureha***.

| Name | Repo | Type | Description | Need Help?
|---|---|---|---|---|
| **[surepy](https://github.com/benleb/surepy) 🐾** | [github.com/benleb/surepy](https://github.com/benleb/surepy) | Python Library | Library to interact with the API of Sure Petcare. Also provides Classes for the various Sure Petcare Devicess. Use this if you write an own python tool/app and want to interact with the Sure Petcare API | [Issues](https://github.com/benleb/surepy/issues) |
| **[surepetcare](https://www.home-assistant.io/integrations/surepetcare)** ![HA Favicon](https://www.home-assistant.io/images/favicon.ico) | [github.com/home-assistant/core](https://github.com/home-assistant/core) | [Home Assistant](https://github.com/home-assistant/core) Integration | **Official Home Assistant Integration** for the Sure Petcare Devices like Doors, Flaps, Feeders, ...  | [Issues](https://github.com/home-assistant/core/issues), [HA Forum](https://community.home-assistant.io) |
| | | | | |
| **[sureha](https://github.com/benleb/sureha)** ~~surepetcarebeta~~ ~~[benleb/surepetcare](https://github.com/benleb/sureha)~~ | [github.com/benleb/sureha](https://github.com/benleb/sureha) | [Home Assistant](https://github.com/home-assistant/core) Integration | Home Assistant Integration developed in my own repo without reviews from the HA Team. This can be installed via [HACS](https://hacs.xyz/) and is something like a preview integration **for advanced users**. Usually this provides more (experimental) features and faster fixes but lacks the code quality (reviews) and such from HA | [Issues](https://github.com/benleb/sureha/issues) |
| | | | | |
| **[pethublocal](https://github.com/plambrechtsen/pethublocal)** | [github.com/plambrechtsen/pethublocal](https://github.com/plambrechtsen/pethublocal) | [Home Assistant](https://github.com/home-assistant/core) Integration | Home Assistant Integration developed by [@plambrechtsen](https://github.com/plambrechtsen) which works **completely independent from Sure Petcare**. Check outs his repo for more information! | [Issues](https://github.com/plambrechtsen/pethublocal/issues), [HA Forum](https://community.home-assistant.io) |
