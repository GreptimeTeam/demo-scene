from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
from opentelemetry.metrics import Observation, Meter


class MetricCollector(BaseModel):
    def make_instruments(self, meter: Meter):
        num_instruments = 0
        for field_name, field_info in self.model_fields.items():
            if not field_info.json_schema_extra:
                continue

            tag_name = field_info.json_schema_extra.get("custom_tag")
            if tag_name == "metric":
                callback = self._create_metric_reader_callback(field_name)
                meter.create_observable_gauge(
                    f"{self.__class__.__name__}_{field_name}",
                    callbacks=[callback],
                )
                num_instruments += 1
        print(f"created {num_instruments} instruments for {self.__class__.__name__}")

    def _create_metric_reader_callback(self, field_name):
        def callback(options):
            value = getattr(self, field_name)
            return [Observation(value=value)] if value is not None else []

        return callback

    def update(self, other: "MetricCollector"):
        for field_name in self.model_fields:
            if hasattr(other, field_name):
                setattr(self, field_name, getattr(other, field_name))


class ChargingStateEnum(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CHARGING = "CHARGING"
    COMPLETED = "COMPLETED"


class ChargeState(MetricCollector):
    battery_level: Optional[int] = Field(None, custom_tag="metric")
    charge_energy_added: Optional[float] = Field(None, custom_tag="metric")
    charge_miles_added_ideal: Optional[float] = Field(None, custom_tag="metric")
    charge_miles_added_rated: Optional[float] = Field(None, custom_tag="metric")
    charger_voltage: Optional[int] = Field(None, custom_tag="metric")
    charger_power: Optional[int] = Field(None, custom_tag="metric")
    charge_rate: Optional[float] = Field(None, custom_tag="metric")
    charger_actual_current: Optional[int] = Field(None, custom_tag="metric")
    timestamp: Optional[int] = Field(None, custom_tag="metric")
    battery_range: Optional[float] = Field(None, custom_tag="metric")
    charge_amps: Optional[int] = Field(None, custom_tag="metric")
    charge_current_request: Optional[int] = Field(None, custom_tag="metric")
    charge_current_request_max: Optional[int] = Field(None, custom_tag="metric")
    charge_limit_soc: Optional[int] = Field(None, custom_tag="metric")
    charge_limit_soc_max: Optional[int] = Field(None, custom_tag="metric")
    charge_limit_soc_min: Optional[int] = Field(None, custom_tag="metric")
    charge_limit_soc_std: Optional[int] = Field(None, custom_tag="metric")
    charger_phases: Optional[int] = Field(None, custom_tag="metric")
    charger_pilot_current: Optional[int] = Field(None, custom_tag="metric")
    est_battery_range: Optional[float] = Field(None, custom_tag="metric")
    ideal_battery_range: Optional[float] = Field(None, custom_tag="metric")
    max_range_charge_counter: Optional[int] = Field(None, custom_tag="metric")
    minutes_to_full_charge: Optional[int] = Field(None, custom_tag="metric")
    scheduled_charging_start_time: Optional[int] = Field(None, custom_tag="metric")
    scheduled_departure_time: Optional[int] = Field(None, custom_tag="metric")
    time_to_full_charge: Optional[float] = Field(None, custom_tag="metric")
    usable_battery_level: Optional[int] = Field(None, custom_tag="metric")

    charging_state: Optional[str] = None
    charge_port_latch: Optional[str] = None
    conn_charge_cable: Optional[str] = None
    fast_charger_brand: Optional[str] = None
    fast_charger_type: Optional[str] = None
    off_peak_charging_times: Optional[str] = None
    preconditioning_times: Optional[str] = None
    scheduled_charging_mode: Optional[str] = None
    charge_port_color: Optional[str] = None
    battery_heater_on: Optional[bool] = None
    charge_enable_request: Optional[bool] = None
    charge_port_cold_weather_mode: Optional[bool] = None
    charge_port_door_open: Optional[bool] = None
    fast_charger_present: Optional[bool] = None
    not_enough_power_to_heat: Optional[bool] = None
    off_peak_charging_enabled: Optional[bool] = None
    preconditioning_enabled: Optional[bool] = None
    scheduled_charging_pending: Optional[bool] = None
    supercharger_session_trip_planner: Optional[bool] = None
    trip_charging: Optional[bool] = None
    user_charge_enable_request: Optional[bool] = None


class DriveState(MetricCollector):
    speed: Optional[float] = Field(None, custom_tag="metric")
    gps_as_of: Optional[int] = Field(None, custom_tag="metric")
    heading: Optional[int] = Field(None, custom_tag="metric")
    latitude: Optional[float] = Field(None, custom_tag="metric")
    longitude: Optional[float] = Field(None, custom_tag="metric")
    native_latitude: Optional[float] = Field(None, custom_tag="metric")
    native_longitude: Optional[float] = Field(None, custom_tag="metric")
    native_location_supported: Optional[int] = Field(None, custom_tag="metric")
    power: Optional[int] = Field(None, custom_tag="metric")
    timestamp: Optional[int] = Field(None, custom_tag="metric")

    native_type: Optional[str] = None
    shift_state: Optional[str] = None
