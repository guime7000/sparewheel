"""GPIO relay: switched on when the service starts (i.e. at boot), then controllable from the web UI.

The logical state is tracked here even when no GPIO hardware exists (dev laptop), so the UI behaves
the same everywhere; hardware failures are logged, never raised.
"""

import logging

from . import config

logger = logging.getLogger(__name__)
_device = None
_state = False


def _get_device():
    global _device
    if _device is None:
        from gpiozero import OutputDevice

        _device = OutputDevice(config.RELAY_GPIO_PIN, active_high=config.RELAY_ACTIVE_HIGH, initial_value=False)
    return _device


def set_state(on: bool) -> bool:
    """Switch the relay. Returns False (state still recorded) if the GPIO could not be driven."""
    global _state
    _state = on
    try:
        device = _get_device()
        device.on() if on else device.off()
        return True
    except Exception:  # no GPIO backend (not a Pi), pin busy, ...
        logger.exception("relay: cannot drive GPIO %s", config.RELAY_GPIO_PIN)
        return False


def is_on() -> bool:
    return _state


def close() -> None:
    global _device
    if _device is not None:
        _device.close()
        _device = None
