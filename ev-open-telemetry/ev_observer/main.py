import time
from ev_observer import scrape_interval, meter, is_mock
from ev_observer.vehicle import VehicleInstrumentor, MockMetricFetcher, TeslaMetricFetcher


def run_collection():
    last_run = 0

    fetcher = None
    if is_mock:
        fetcher = MockMetricFetcher()
    else:
        fetcher = TeslaMetricFetcher()

    instumentor = VehicleInstrumentor(fetcher, meter)

    while True:
        current_time = time.time()
        if current_time - last_run >= scrape_interval:
            instumentor.observe()
            last_run = current_time
        time.sleep(1)


if __name__ == "__main__":
    run_collection()
