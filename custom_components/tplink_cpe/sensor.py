"""Sensor platform for TP-Link CPE (SSH)."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    UnitOfDataRate,
    UnitOfFrequency,
    UnitOfInformation,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import parser
from .const import (
    CONF_HOST,
    CONF_MAC,
    DEFAULT_MODEL,
    DOMAIN,
    EXTRA_THROUGHPUT_IFACES,
    MANUFACTURER,
)
from .coordinator import TpLinkCpeConfigEntry, TpLinkCpeCoordinator


@dataclass(frozen=True, kw_only=True)
class TpLinkCpeSensorDescription(SensorEntityDescription):
    """Describes a sensor and how to read it from the data dict."""

    value_fn: Callable[[dict], object]


def _uptime_to_dt(data: dict) -> datetime | None:
    secs = data.get(parser.KEY_UPTIME)
    if secs is None:
        return None
    return datetime.now(timezone.utc) - timedelta(seconds=secs)


SENSORS: tuple[TpLinkCpeSensorDescription, ...] = (
    TpLinkCpeSensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=_uptime_to_dt,
    ),
    TpLinkCpeSensorDescription(
        key="load_1m",
        translation_key="load_1m",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda d: d.get(parser.KEY_LOAD_1),
    ),
    TpLinkCpeSensorDescription(
        key="load_5m",
        translation_key="load_5m",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda d: d.get(parser.KEY_LOAD_5),
    ),
    TpLinkCpeSensorDescription(
        key="load_15m",
        translation_key="load_15m",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        suggested_display_precision=2,
        value_fn=lambda d: d.get(parser.KEY_LOAD_15),
    ),
    TpLinkCpeSensorDescription(
        key="memory_used_percent",
        translation_key="memory_used_percent",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: d.get(parser.KEY_MEM_PCT),
    ),
    TpLinkCpeSensorDescription(
        key="essid",
        translation_key="essid",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get(parser.KEY_ESSID),
    ),
    TpLinkCpeSensorDescription(
        key="mode",
        translation_key="mode",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get(parser.KEY_MODE),
    ),
    TpLinkCpeSensorDescription(
        key="channel",
        translation_key="channel",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get(parser.KEY_CHANNEL),
    ),
    TpLinkCpeSensorDescription(
        key="frequency",
        translation_key="frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        native_unit_of_measurement=UnitOfFrequency.GIGAHERTZ,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get(parser.KEY_FREQ),
    ),
    TpLinkCpeSensorDescription(
        key="bit_rate",
        translation_key="bit_rate",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(parser.KEY_BITRATE),
    ),
    TpLinkCpeSensorDescription(
        key="tx_power",
        translation_key="tx_power",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get(parser.KEY_TXPOWER),
    ),
    TpLinkCpeSensorDescription(
        key="signal",
        translation_key="signal",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(parser.KEY_SIGNAL),
    ),
    TpLinkCpeSensorDescription(
        key="noise",
        translation_key="noise",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get(parser.KEY_NOISE),
    ),
    TpLinkCpeSensorDescription(
        key="link_quality",
        translation_key="link_quality",
        native_unit_of_measurement="%",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(parser.KEY_QUALITY),
    ),
    TpLinkCpeSensorDescription(
        key="connected_clients",
        translation_key="connected_clients",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(parser.KEY_CLIENTS),
    ),
    TpLinkCpeSensorDescription(
        key="avg_client_rssi",
        translation_key="avg_client_rssi",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(parser.KEY_RSSI_AVG),
    ),
    TpLinkCpeSensorDescription(
        key="min_client_rssi",
        translation_key="min_client_rssi",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get(parser.KEY_RSSI_MIN),
    ),
)


def _throughput_descs(wifi_if: str) -> list[TpLinkCpeSensorDescription]:
    descs: list[TpLinkCpeSensorDescription] = []
    for iface in [wifi_if, *EXTRA_THROUGHPUT_IFACES]:
        for direction in ("rx", "tx"):
            descs.append(
                TpLinkCpeSensorDescription(
                    key=f"{iface}_{direction}_mbps",
                    name=f"{iface} {direction.upper()} rate",
                    icon=(
                        "mdi:download-network-outline"
                        if direction == "rx"
                        else "mdi:upload-network-outline"
                    ),
                    native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
                    state_class=SensorStateClass.MEASUREMENT,
                    suggested_display_precision=2,
                    value_fn=(
                        lambda d, i=iface, dr=direction: d.get(
                            parser.KEY_THROUGHPUT, {}
                        ).get(i, {}).get(f"{dr}_mbps")
                    ),
                )
            )
            descs.append(
                TpLinkCpeSensorDescription(
                    key=f"{iface}_{direction}_total",
                    name=f"{iface} {direction.upper()} total",
                    icon="mdi:download" if direction == "rx" else "mdi:upload",
                    device_class=SensorDeviceClass.DATA_SIZE,
                    native_unit_of_measurement=UnitOfInformation.BYTES,
                    state_class=SensorStateClass.TOTAL_INCREASING,
                    entity_category=EntityCategory.DIAGNOSTIC,
                    entity_registry_enabled_default=False,
                    value_fn=(
                        lambda d, i=iface, dr=direction: d.get(
                            parser.KEY_IFACES, {}
                        ).get(i, {}).get(f"{dr}_bytes")
                    ),
                )
            )
    return descs


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TpLinkCpeConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    descriptions = [*SENSORS, *_throughput_descs(coordinator.wifi_if)]
    async_add_entities(
        TpLinkCpeSensor(coordinator, entry, desc) for desc in descriptions
    )


class TpLinkCpeSensor(CoordinatorEntity[TpLinkCpeCoordinator], SensorEntity):
    """A single sensor backed by the coordinator data dict."""

    entity_description: TpLinkCpeSensorDescription
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: TpLinkCpeCoordinator,
        entry: TpLinkCpeConfigEntry,
        description: TpLinkCpeSensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        mac = entry.data[CONF_MAC]
        self._attr_unique_id = f"{mac}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, mac)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=DEFAULT_MODEL,
            configuration_url=f"http://{entry.data[CONF_HOST]}",
        )

    @property
    def available(self) -> bool:
        return (
            super().available
            and bool(self.coordinator.data)
            and self.coordinator.data.get(parser.KEY_ONLINE, False)
        )

    @property
    def native_value(self):
        if not self.coordinator.data:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
