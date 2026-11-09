"""GPIO relay, switched on when the service starts (i.e. at boot)."""

import logging

from . import config

logger = logging.getLogger(__name__)
_device = None


def on() -> bool:
    """Energise the relay. Returns False (and logs) if no GPIO is available."""
    global _device
    try:
        from gpiozero import OutputDevice

        _device = OutputDevice(config.RELAY_GPIO_PIN, active_high=config.RELAY_ACTIVE_HIGH, initial_value=False)
        _device.on()
        return True
    except Exception:  # no GPIO backend (not a Pi), pin busy, ...
        logger.exception("relay: cannot drive GPIO %s", config.RELAY_GPIO_PIN)
        return False


def off() -> None:
    if _device is not None:
        _device.off()
        _device.close()
