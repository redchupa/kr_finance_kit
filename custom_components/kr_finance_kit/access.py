"""Match access to the HA sensor exposing the full holdings breakdown."""
from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN


def can_read_holdings(hass, user) -> bool:
    if user is None:
        return False
    if user.is_admin:
        return True
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{DOMAIN}_portfolio_krw_pl"
    )
    return bool(entity_id and user.permissions.check_entity(entity_id, POLICY_READ))
