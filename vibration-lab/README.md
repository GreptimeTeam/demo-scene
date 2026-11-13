# Vibration Lab

A synthetic rotating-machine signal experiment: switch between normal operation, imbalance, and looseness, then inspect the waveform, frequency spectrum, RMS, peak acceleration, and crest factor in Grafana.

## Run

Requires Docker Compose 2.24 or later. Run one demo at a time: the default ports are shared with other demos.

```sh
docker compose up -d --build --wait
```

Open the [controls](http://localhost:8080) and [Grafana](http://localhost:3000). Both select English or Chinese from the browser's preferred language; Grafana also provides language links. Data appears within a few seconds.

| Scenario | Signal |
| --- | --- |
| Normal | 30 Hz rotation with low-amplitude noise |
| Imbalance | Larger 30 Hz component |
| Looseness | 60/90 Hz harmonics and periodic impulses |

The source is simulated acceleration in g, sampled at 1024 Hz. Each one-second window contains 1024 samples. NumPy computes a Hann-windowed FFT with 1 Hz frequency spacing and amplitude normalization. Scenario names describe the injected signal patterns; this is not a calibrated equipment diagnostic.

## Storage

| Table | Primary key | Data | TTL |
| --- | --- | --- | --- |
| `vibration_raw` | `device` | Nanosecond timestamps and acceleration | 15 minutes |
| `vibration_spectrum` | `device, frequency` | 513 frequency bins per window | 15 minutes |
| `vibration_features` | `device` | RMS, peak, crest factor, and scenario per window | 1 day |

All tables have a time index. Measurement values and the scenario are fields. The spectrum's frequency tag distinguishes bins sharing the same window timestamp. Nanosecond timestamps preserve the 1024 Hz samples without collisions from millisecond rounding. Raw signals and spectra expire sooner than the compact feature rows.

```sql
SELECT greptime_timestamp, rms, peak, crest_factor
FROM vibration_features
WHERE device = 'motor-01'
ORDER BY greptime_timestamp DESC
LIMIT 10;
```

```sh
docker compose logs app
docker compose down
```

Signal tests:

```sh
docker compose run --rm -v "$PWD/app:/app:ro" app python -m unittest discover -s /app -v
```
