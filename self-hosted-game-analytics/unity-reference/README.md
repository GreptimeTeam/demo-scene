# Unity Reference Client

A reference `TelemetryClient.cs` you can drop into a Unity project to send
game events to the analytics server used in this demo.

## Requirements

- Unity 2022 LTS or newer (Unity 6000.x should also work — not tested)
- API Compatibility Level: **.NET Standard 2.1** (Unity default; no changes needed)
- No external packages required — only `UnityEngine` (for `JsonUtility`) and `UnityEngine.Networking` (for `UnityWebRequest`)

## Install

1. Copy `TelemetryClient.cs` into `Assets/Scripts/Telemetry/` of your Unity project.
2. In your first scene, create an empty GameObject named `Telemetry` and
   attach the `TelemetryClient` component to it.
3. In the inspector, set `analyticsUrl` to the URL where the demo's
   analytics server is reachable (e.g. `http://localhost:8080` when running
   `docker compose up` from this demo).

## Use

```csharp
using Greptime.Unity.Telemetry;

// Fire and forget — buffered and batched internally.
Telemetry.Track("level_started", levelId: "forest_1");

Telemetry.Track(
    eventType: "level_completed",
    levelId: "forest_1",
    durationMs: 45230,
    score: 1250,
    goldDelta: 42);

Telemetry.Track(
    eventType: "player_death",
    levelId: "boss_1",
    durationMs: 20100,
    reason: "enemy_melee");

Telemetry.Track(
    eventType: "iap_purchase",
    amountUsd: 4.99);
```

By default the client also emits a `perf_sample` event every 2 seconds
containing FPS and managed heap size, so the Grafana dashboards have
something to show without requiring a full OpenTelemetry SDK integration.

## Reliability

- Events are batched in memory and flushed when any of these happen:
  - `maxBatchSize` (default 50) is reached
  - `flushInterval` seconds (default 2s) elapse
  - **the app goes to background** (`OnApplicationPause(true)`)
- Backgrounding is the most reliable "player leaves" boundary on mobile
  — the OS can kill the process afterwards without ever invoking
  `OnApplicationQuit`.
- Flush on quit is **best-effort only**. Unity typically tears the
  player down before a coroutine completes, and a hard crash / `kill -9`
  bypasses `OnApplicationQuit` entirely. For guaranteed delivery across
  crashes, OS kills, and unclean quits, persist the pending buffer to
  `PlayerPrefs` (or a file) on pause/quit and replay it on next `Awake`.
  This reference client keeps things in-memory to stay minimal — wire
  persistence in when you fork it for production.

## Why not the GreptimeDB .NET SDK directly?

The GreptimeDB .NET Ingester SDK targets `net8.0` and depends on
`Grpc.Net.Client` + Apache Arrow, none of which load cleanly in Unity's
Mono / IL2CPP runtime (still on .NET Standard 2.1 through Unity 6.7).
This is the same reason commercial SDKs such as GameAnalytics, Firebase
Analytics and Unity Analytics all use a thin HTTP client on the game side
and do the heavy ingestion work on a server. The analytics server in this
demo is the server side; `TelemetryClient.cs` is the thin client.

When Unity 6.8 ships CoreCLR and the .NET SDK is consumable directly from
the engine, this file can be replaced by a direct `GreptimeClient` call.

## Adding OpenTelemetry metrics from Unity

For full OTLP metrics from inside a build (FPS histograms, memory, custom
counters), use a community OpenTelemetry-for-Unity package that ships a
netstandard2.1-compatible exporter, and point its OTLP endpoint at
`http://<greptimedb-host>:4000/v1/otlp/v1/metrics`. The simulator in this
demo emits the same metric shape (`game.fps`, `game.frame_time`,
`game.memory`, `game.draw_calls` with `player_id`, `platform`,
`device_model`, `scene_name`, `game_version`, `session_id` attributes) so
dashboards will work transparently.
