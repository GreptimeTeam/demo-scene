// Unity Telemetry Client — reference integration for sending game telemetry
// to the analytics server backed by GreptimeDB.
//
// Drop this single file into Assets/Scripts/Telemetry/ of a Unity project
// (Unity 2022 LTS or newer). No external packages required; only UnityEngine
// and UnityEngine.Networking.
//
// Usage:
//   1. Create an empty GameObject in your first scene and attach TelemetryClient
//      as a component. Fill in `analyticsUrl` in the inspector.
//   2. Call Telemetry.Track("level_started", ...) etc. from your gameplay code.
//   3. The client batches events in memory and flushes every flushInterval
//      seconds or when the buffer fills, whichever comes first.
//
// This file covers business events via REST. For OpenTelemetry metrics
// (FPS / memory) there is a community OpenTelemetry-for-Unity package that
// works with netstandard2.1; until you wire that in, you can reuse Track()
// to POST a synthetic metric event — the analytics server accepts both.

using System;
using System.Collections;
using System.Collections.Generic;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace Greptime.Unity.Telemetry
{
    [DisallowMultipleComponent]
    public sealed class TelemetryClient : MonoBehaviour
    {
        [Tooltip("Base URL of the analytics server. e.g. http://localhost:8080")]
        public string analyticsUrl = "http://localhost:8080";

        [Tooltip("Game version string, e.g. 1.4.2")]
        public string gameVersion = "1.0.0";

        [Tooltip("Max events held in memory before forcing a flush")]
        public int maxBatchSize = 50;

        [Tooltip("Seconds between periodic flushes")]
        public float flushInterval = 2.0f;

        [Tooltip("Include client FPS every flush as a synthetic perf_sample event")]
        public bool emitFpsSample = true;

        private static TelemetryClient _instance;
        private readonly List<EventPayload> _buffer = new List<EventPayload>();
        private readonly object _lock = new object();
        private string _sessionId;
        private string _playerId;
        private string _platform;
        private string _deviceModel;
        private float _fpsAccum;
        private int _fpsFrames;

        public static TelemetryClient Instance => _instance;

        private void Awake()
        {
            if (_instance != null && _instance != this)
            {
                Destroy(gameObject);
                return;
            }
            _instance = this;
            DontDestroyOnLoad(gameObject);

            _sessionId = Guid.NewGuid().ToString("N");
            _playerId = PlayerPrefs.GetString("greptime.player_id", null);
            if (string.IsNullOrEmpty(_playerId))
            {
                _playerId = "player_" + Guid.NewGuid().ToString("N").Substring(0, 8);
                PlayerPrefs.SetString("greptime.player_id", _playerId);
            }
            _platform = ResolvePlatform();
            _deviceModel = SystemInfo.deviceModel;

            StartCoroutine(FlushLoop());
        }

        private static string ResolvePlatform()
        {
            switch (Application.platform)
            {
                case RuntimePlatform.IPhonePlayer: return "ios";
                case RuntimePlatform.Android: return "android";
                case RuntimePlatform.WindowsPlayer:
                case RuntimePlatform.LinuxPlayer:
                case RuntimePlatform.OSXPlayer:
                case RuntimePlatform.WindowsEditor:
                case RuntimePlatform.OSXEditor:
                case RuntimePlatform.LinuxEditor:
                    return "pc";
                case RuntimePlatform.PS5:
                case RuntimePlatform.XboxOne:
                case RuntimePlatform.Switch:
                    return "console";
                default: return Application.platform.ToString().ToLowerInvariant();
            }
        }

        private void Update()
        {
            if (!emitFpsSample) return;
            _fpsAccum += Time.unscaledDeltaTime;
            _fpsFrames++;
        }

        public void Track(
            string eventType,
            string levelId = null,
            double? durationMs = null,
            long? score = null,
            long? goldDelta = null,
            double? amountUsd = null,
            string reason = null)
        {
            var payload = new EventPayload
            {
                event_type = eventType,
                platform = _platform,
                game_version = gameVersion,
                player_id = _playerId,
                session_id = _sessionId,
                level_id = levelId,
                duration_ms = durationMs,
                score = score,
                gold_delta = goldDelta,
                amount_usd = amountUsd,
                reason = reason,
                timestamp_ms = NowUnixMs(),
            };

            lock (_lock)
            {
                _buffer.Add(payload);
                if (_buffer.Count >= maxBatchSize)
                {
                    StartCoroutine(FlushNow());
                }
            }
        }

        private IEnumerator FlushLoop()
        {
            var wait = new WaitForSecondsRealtime(flushInterval);
            while (true)
            {
                yield return wait;
                EmitFpsSampleIfNeeded();
                yield return FlushNow();
            }
        }

        private void EmitFpsSampleIfNeeded()
        {
            if (!emitFpsSample || _fpsFrames == 0) return;
            float avgDt = _fpsAccum / _fpsFrames;
            float fps = avgDt > 0 ? 1f / avgDt : 0f;
            _fpsAccum = 0;
            _fpsFrames = 0;

            double memMb = (System.GC.GetTotalMemory(false) / 1024.0) / 1024.0;

            Track(
                eventType: "perf_sample",
                reason: $"fps={fps:F1};mem_mb={memMb:F1}");
        }

        private IEnumerator FlushNow()
        {
            List<EventPayload> batch;
            lock (_lock)
            {
                if (_buffer.Count == 0) yield break;
                batch = new List<EventPayload>(_buffer);
                _buffer.Clear();
            }

            string json = BuildJsonArray(batch);
            var url = analyticsUrl.TrimEnd('/') + "/api/events";

            using (var req = new UnityWebRequest(url, UnityWebRequest.kHttpVerbPOST))
            {
                byte[] body = Encoding.UTF8.GetBytes(json);
                req.uploadHandler = new UploadHandlerRaw(body);
                req.downloadHandler = new DownloadHandlerBuffer();
                req.SetRequestHeader("Content-Type", "application/json");
                req.timeout = 10;
                yield return req.SendWebRequest();
                if (req.result != UnityWebRequest.Result.Success)
                {
                    Debug.LogWarning($"[Telemetry] flush failed: {req.error} (dropped {batch.Count})");
                }
            }
        }

        private void OnApplicationQuit()
        {
            if (Application.isPlaying)
            {
                StartCoroutine(FlushNow());
            }
        }

        private static long NowUnixMs() =>
            (long)(DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalMilliseconds;

        private static string BuildJsonArray(List<EventPayload> batch)
        {
            var sb = new StringBuilder(batch.Count * 256);
            sb.Append('[');
            for (int i = 0; i < batch.Count; i++)
            {
                if (i > 0) sb.Append(',');
                batch[i].AppendJson(sb);
            }
            sb.Append(']');
            return sb.ToString();
        }

        private sealed class EventPayload
        {
            public string event_type;
            public string platform;
            public string game_version;
            public string player_id;
            public string session_id;
            public string level_id;
            public double? duration_ms;
            public long? score;
            public long? gold_delta;
            public double? amount_usd;
            public string reason;
            public long timestamp_ms;

            public void AppendJson(StringBuilder sb)
            {
                sb.Append('{');
                AppendField(sb, "event_type", event_type, first: true);
                AppendField(sb, "platform", platform);
                AppendField(sb, "game_version", game_version);
                AppendField(sb, "player_id", player_id);
                AppendField(sb, "session_id", session_id);
                if (level_id != null) AppendField(sb, "level_id", level_id);
                if (duration_ms.HasValue) AppendField(sb, "duration_ms", duration_ms.Value);
                if (score.HasValue) AppendField(sb, "score", score.Value);
                if (gold_delta.HasValue) AppendField(sb, "gold_delta", gold_delta.Value);
                if (amount_usd.HasValue) AppendField(sb, "amount_usd", amount_usd.Value);
                if (reason != null) AppendField(sb, "reason", reason);
                AppendField(sb, "timestamp_ms", timestamp_ms);
                sb.Append('}');
            }

            private static void AppendField(StringBuilder sb, string key, string val, bool first = false)
            {
                if (!first) sb.Append(',');
                sb.Append('"').Append(key).Append("\":");
                if (val == null) { sb.Append("null"); return; }
                sb.Append('"');
                foreach (var c in val)
                {
                    if (c == '"' || c == '\\') sb.Append('\\').Append(c);
                    else if (c == '\n') sb.Append("\\n");
                    else if (c == '\r') sb.Append("\\r");
                    else if (c == '\t') sb.Append("\\t");
                    else sb.Append(c);
                }
                sb.Append('"');
            }

            private static void AppendField(StringBuilder sb, string key, double val, bool first = false)
            {
                if (!first) sb.Append(',');
                sb.Append('"').Append(key).Append("\":").Append(val.ToString("R", System.Globalization.CultureInfo.InvariantCulture));
            }

            private static void AppendField(StringBuilder sb, string key, long val, bool first = false)
            {
                if (!first) sb.Append(',');
                sb.Append('"').Append(key).Append("\":").Append(val.ToString(System.Globalization.CultureInfo.InvariantCulture));
            }
        }
    }

    public static class Telemetry
    {
        public static void Track(
            string eventType,
            string levelId = null,
            double? durationMs = null,
            long? score = null,
            long? goldDelta = null,
            double? amountUsd = null,
            string reason = null)
        {
            var client = TelemetryClient.Instance;
            if (client == null)
            {
                Debug.LogWarning("[Telemetry] TelemetryClient not initialized; event dropped");
                return;
            }
            client.Track(eventType, levelId, durationMs, score, goldDelta, amountUsd, reason);
        }
    }
}
