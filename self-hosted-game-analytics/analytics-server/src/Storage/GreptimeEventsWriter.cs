using AnalyticsServer.Models;
using GreptimeDB.Ingester.Client;
using GreptimeDB.Ingester.Table;
using GreptimeDB.Ingester.Types;

namespace AnalyticsServer.Storage;

public interface IGreptimeEventsWriter
{
    Task<uint> WriteBatchAsync(IReadOnlyList<GameEvent> events, CancellationToken ct);
}

public sealed class GreptimeEventsWriter(GreptimeClient client, ILogger<GreptimeEventsWriter> logger)
    : IGreptimeEventsWriter
{
    private const string TableName = "game_events";

    public async Task<uint> WriteBatchAsync(IReadOnlyList<GameEvent> events, CancellationToken ct)
    {
        if (events.Count == 0)
        {
            return 0;
        }

        var builder = new TableBuilder(TableName)
            .AddTag("event_type", ColumnDataType.String)
            .AddTag("platform", ColumnDataType.String)
            .AddTag("game_version", ColumnDataType.String)
            .AddTag("player_id", ColumnDataType.String)
            .AddTag("session_id", ColumnDataType.String)
            .AddTag("level_id", ColumnDataType.String)
            .AddField("duration_ms", ColumnDataType.Float64)
            .AddField("score", ColumnDataType.Int64)
            .AddField("gold_delta", ColumnDataType.Int64)
            .AddField("amount_usd", ColumnDataType.Float64)
            .AddField("reason", ColumnDataType.String)
            .AddTimestamp("ts", ColumnDataType.TimestampMillisecond);

        foreach (var e in events)
        {
            var ts = e.TimestampMs.HasValue
                ? DateTimeOffset.FromUnixTimeMilliseconds(e.TimestampMs.Value).UtcDateTime
                : DateTime.UtcNow;

            builder.AddRow(
                e.EventType,
                e.Platform,
                e.GameVersion,
                e.PlayerId,
                e.SessionId,
                e.LevelId ?? string.Empty,
                e.DurationMs ?? 0.0,
                e.Score ?? 0L,
                e.GoldDelta ?? 0L,
                e.AmountUsd ?? 0.0,
                e.Reason ?? string.Empty,
                ts);
        }

        var table = builder.Build();
        var affected = await client.WriteAsync(table, ct);
        logger.LogInformation("Wrote {Affected} events to GreptimeDB", affected);
        return affected;
    }
}
