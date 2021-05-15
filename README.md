# surepetcare

> Flap lock states are now reported state with an _ again - sorry for changing!

**dev** branch of the Home Assistant surepetcare integration. dev branch means "maybe it works, maybe not..." ;)

...and maybe you may have to use the latest (pre) release or even the dev branch of https://github.com/benleb/surepy!

...and you have to change `surepetcare` in your `configuration.yaml` to `surepetcarebeta` if you used the official integration before!

##### ...and enable the debug logging in `configuration.yaml` if something does not work as expected!

```yaml
# logging
logger:
  default: info
  logs:
    surepy: debug
    custom_components.surepetcarebeta: debug
    custom_components.surepetcarebeta.binary_sensor: debug
    custom_components.surepetcarebeta.sensor: debug
```
