This is a fork from the original SureHA custom component provided by @benleb.
The goal of this fork is to provide improvements on some areas...
Unfortunately, I don't own some of the devices, like felaqua or feeder, therefore, I cannot validate and test changes I've made there.

If you are interested in testing and providing feedback, please let me know in the discussions.

--------------------
Original Readme:
------

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
| Voltage             | 5.09              |
| Voltage per battery | 1.27              |
| Alt-battery         | 16.82560000000002 |
</details>

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
    - lock_state = 
  
 example:
 ```yaml
 service: sureha.set_lock_state
data:
  flap_id: 123456
  lock_state: locked
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
