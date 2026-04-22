using System.Text.Json.Serialization;

namespace AnalyticsServer.Models;

public sealed record GameEvent(
    [property: JsonPropertyName("event_type")] string EventType,
    [property: JsonPropertyName("platform")] string Platform,
    [property: JsonPropertyName("game_version")] string GameVersion,
    [property: JsonPropertyName("player_id")] string PlayerId,
    [property: JsonPropertyName("session_id")] string SessionId,
    [property: JsonPropertyName("level_id")] string? LevelId,
    [property: JsonPropertyName("duration_ms")] double? DurationMs,
    [property: JsonPropertyName("score")] long? Score,
    [property: JsonPropertyName("gold_delta")] long? GoldDelta,
    [property: JsonPropertyName("amount_usd")] double? AmountUsd,
    [property: JsonPropertyName("reason")] string? Reason,
    [property: JsonPropertyName("timestamp_ms")] long? TimestampMs);
