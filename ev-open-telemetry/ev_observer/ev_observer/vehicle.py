import os
import sys
import random
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Optional
from pydantic import BaseModel
from requests import HTTPError
from opentelemetry.metrics import Meter
from opentelemetry.util.types import Attributes
import teslapy

from ev_observer.metrics import (
    ChargeState,
    DriveState,
    ChargingStateEnum,
    MetricCollector,
)


class EVMetricData(BaseModel):
    attributes: Optional[Attributes] = None
    charge_state: ChargeState = ChargeState()
    drive_state: DriveState = DriveState()
    # ... any future states can be added here ...

    def init_instruments(self, meter: Meter):
        for attr, value in self.__dict__.items():
            if isinstance(value, MetricCollector):
                value.make_instruments(meter)

    def update(self, new_data: "EVMetricData"):
        for metric_type, value in self.__dict__.items():
            if hasattr(new_data, metric_type) and isinstance(value, MetricCollector):
                metric_state = getattr(self, metric_type)
                metric_state.attributes = new_data.attributes
                getattr(self, metric_type).update_values(getattr(new_data, metric_type))


class AbstractVehicleDataFetcher(ABC):
    @abstractmethod
    def refresh(self) -> EVMetricData:
        pass


class VehicleInstrumentor:
    ev_metrics: EVMetricData
    fetcher: AbstractVehicleDataFetcher

    def __init__(self, fetcher: AbstractVehicleDataFetcher, meter: Meter):
        self.metrics = EVMetricData()
        self.metrics.init_instruments(meter)
        self.fetcher = fetcher

    def observe(self):
        print(f"refreshing data at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        ev_metric_update = self.fetcher.refresh()
        self.metrics.update(ev_metric_update)


class TeslaMetricFetcher(AbstractVehicleDataFetcher):
    def refresh(self) -> EVMetricData:
        tesla_user_email = os.getenv("TESLA_USER_EMAIL")
        if not tesla_user_email:
            print("TESLA_USER_EMAIL env var is not set", file=sys.stderr)
            exit(1)

        with teslapy.Tesla(tesla_user_email) as tesla:
            try:
                vehicles = tesla.vehicle_list()
                main_vehicle = vehicles[0]

                res = main_vehicle.get_vehicle_data()
                return EVMetricData(
                    charge_state=res["charge_state"],
                    drive_state=res["drive_state"],
                    attributes={"vehicle_id": main_vehicle["display_name"]},
                )
            except HTTPError as e:
                if e.response.status_code == 408:
                    # Silently ignore 408 Request Sleeping error
                    print("car is sleeping")
                    return EVMetricData(charge_state=ChargeState(), drive_state=DriveState())
                else:
                    raise


class MockMetricFetcher(AbstractVehicleDataFetcher):
    def __init__(self):
        self.battery_level = 70
        self.charging = False
        self.latitude = 37.7749
        self.longitude = -122.4194
        self.speed = 0

    def refresh(self) -> EVMetricData:
        return EVMetricData(
            charge_state=self.get_charge_state(), drive_state=self.get_drive_state()
        )

    def get_charge_state(self) -> ChargeState:
        if self.charging:
            self.battery_level = min(100, self.battery_level + random.uniform(0.1, 1.0))
        else:
            self.battery_level = max(0, self.battery_level - random.uniform(0.05, 0.5))

        return ChargeState(
            charging_state=(
                ChargingStateEnum.CHARGING if self.charging else ChargingStateEnum.DISCONNECTED
            ),
            charge_energy_added=random.uniform(0, 10),
            charge_miles_added_ideal=random.uniform(0, 30),
            charge_miles_added_rated=random.uniform(0, 25),
            charger_voltage=random.randint(110, 240),
            charger_power=random.randint(1, 20),
            charge_rate=random.uniform(10, 50),
            charger_actual_current=random.randint(10, 40),
            timestamp=int(datetime.now().timestamp()),
        )

    def get_drive_state(self) -> DriveState:
        if self.speed > 0:
            self.latitude += random.uniform(-0.001, 0.001)
            self.longitude += random.uniform(-0.001, 0.001)

        return DriveState(
            speed=self.speed,
            gps_as_of=int(datetime.now().timestamp()),
            heading=random.randint(0, 359),
            latitude=self.latitude,
            longitude=self.longitude,
            native_latitude=self.latitude,
            native_longitude=self.longitude,
            native_location_supported=1,
            native_type="wgs",
            power=random.randint(-10, 100),
            shift_state="D" if self.speed > 0 else "P",
            timestamp=int(datetime.now().timestamp()),
        )

    def start_charging(self):
        self.charging = True

    def stop_charging(self):
        self.charging = False

    def set_speed(self, speed: float):
        self.speed = speed
