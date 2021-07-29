# SureHA

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
