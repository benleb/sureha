"""Constants for the Sure Petcare component."""
DOMAIN = "sureha"

SPC = "spc"

# platforms
TOPIC_UPDATE = f"{DOMAIN}_data_update"

# sure petcare api
SURE_API_TIMEOUT = 60

# device info
SURE_MANUFACTURER = "Sure Petcare"

# pet door c-cell battery voltage
SURE_BATT_VOLTAGE_FULL = 1.6
SURE_BATT_VOLTAGE_LOW = 1.25
SURE_BATT_VOLTAGE_DIFF = SURE_BATT_VOLTAGE_FULL - SURE_BATT_VOLTAGE_LOW

# lock state service
SERVICE_SET_LOCK_STATE = "set_lock_state"
ATTR_FLAP_ID = "flap_id"
ATTR_LOCK_STATE = "lock_state"
