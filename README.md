# Naming confusion for *surepetcarebeta* users 🐾 🤪 🤦

Sorry for the bad naming and resulting confusion and chaos 🙄 To "fix" this, I will do a rename of the *sureha* integration (formerly *surepetcarebeta*). If you are a user of the *surepetcarebeta* integration you will have to do some manual work to update your setup (row 3). I will post an update with an "upgrade path" until 1. july, please do not try to update the integration in the meantime ツ
| Name | Repo | Type | Description | Need Help?
|---|---|---|---|---|
| **[surepy](https://github.com/benleb/surepy) 🐾** | [github.com/benleb/surepy](https://github.com/benleb/surepy) | Python Library | Library to interact with the API of Sure Petcare. Also provides Classes for the various Sure Petcare Devicess. Use this if you write an own python tool/app and want to interact with the Sure Petcare API | [Issues](https://github.com/benleb/surepy/issues) |
| **[surepetcare](https://www.home-assistant.io/integrations/surepetcare)** ![HA Favicon](https://www.home-assistant.io/images/favicon.ico) | [github.com/home-assistant/core](https://github.com/home-assistant/core) | [Home Assistant](https://github.com/home-assistant/core) Integration | **Official Home Assistant Integration** for the Sure Petcare Devices like Doors, Flaps, Feeders, ...  | [Issues](https://github.com/home-assistant/core/issues), [HA Forum](https://community.home-assistant.io) |
| | | | | |
| **[sureha](https://github.com/benleb/sureha)** ~~surepetcarebeta~~ ~~[benleb/surepetcare](https://github.com/benleb/sureha)~~ | [github.com/benleb/sureha](https://github.com/benleb/sureha) | [Home Assistant](https://github.com/home-assistant/core) Integration | Home Assistant Integration developed in my own repo without reviews from the HA Team. This can be installed via [HACS](https://hacs.xyz/) and is something like a preview integration **for advanced users**. Usually this provides more (experimental) features and faster fixes but lacks the code quality (reviews) and such from HA | [Issues](https://github.com/benleb/sureha/issues) |
| | | | | |
| **[pethublocal](https://github.com/plambrechtsen/pethublocal)** | [github.com/plambrechtsen/pethublocal](https://github.com/plambrechtsen/pethublocal) | [Home Assistant](https://github.com/home-assistant/core) Integration | Home Assistant Integration developed by [@plambrechtsen](https://github.com/plambrechtsen) which works **completely independent from Sure Petcare**. Check outs his repo for more information! | [Issues](https://github.com/plambrechtsen/pethublocal/issues), [HA Forum](https://community.home-assistant.io) |


---

# SureHA

> Flap lock states are now reported state with an _ again - sorry for changing!

Something like an enhanced variant with sneak-previews of upcoming features of the official Home Assistant surepetcare integration!

...and maybe you may have to use the latest (pre) release or even the dev branch of https://github.com/benleb/surepy!


##### ...and enable the debug logging in `configuration.yaml` if something does not work as expected!

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
