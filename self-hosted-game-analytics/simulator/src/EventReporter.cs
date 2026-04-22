using System.Net.Http.Json;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Threading.Channels;
using Microsoft.Extensions.Logging;

namespace GameSimulator;

public sealed class EventReporter : IAsyncDisposable
{
    private readonly HttpClient _http;
    private readonly string _endpoint;
    private readonly Channel<EventPayload> _channel;
    private readonly Task _drainTask;
    private readonly CancellationTokenSource _cts = new();
    private readonly ILogger _log;
    private readonly int _batchSize;
    private readonly TimeSpan _flushInterval;

    public EventReporter(string analyticsUrl, ILogger log, int batchSize = 50, int flushIntervalMs = 500)
    {
        _http = new HttpClient { Timeout = TimeSpan.FromSeconds(10) };
        _endpoint = analyticsUrl.TrimEnd('/') + "/api/events";
        _channel = Channel.CreateBounded<EventPayload>(new BoundedChannelOptions(10_000)
        {
            FullMode = BoundedChannelFullMode.DropOldest,
            SingleReader = true,
        });
        _log = log;
        _batchSize = batchSize;
        _flushInterval = TimeSpan.FromMilliseconds(flushIntervalMs);
        _drainTask = Task.Run(DrainLoopAsync);
    }

    public async ValueTask EnqueueAsync(Events.IGameEvent evt, CancellationToken ct)
    {
        var payload = new EventPayload(
            evt.EventType,
            evt.Player.Platform,
            evt.Player.GameVersion,
            evt.Player.PlayerId,
            evt.Player.SessionId,
            evt.LevelId,
            evt.DurationMs,
            evt.Score,
            evt.GoldDelta,
            evt.AmountUsd,
            evt.Reason,
            new DateTimeOffset(evt.Timestamp, TimeSpan.Zero).ToUnixTimeMilliseconds());

        await _channel.Writer.WriteAsync(payload, ct);
    }

    private async Task DrainLoopAsync()
    {
        var buffer = new List<EventPayload>(_batchSize);
        var lastFlush = DateTime.UtcNow;

        while (!_cts.IsCancellationRequested)
        {
            try
            {
                var hasItem = await _channel.Reader.WaitToReadAsync(_cts.Token);
                if (!hasItem)
                {
                    break;
                }

                while (buffer.Count < _batchSize && _channel.Reader.TryRead(out var item))
                {
                    buffer.Add(item);
                }

                var now = DateTime.UtcNow;
                if (buffer.Count >= _batchSize || now - lastFlush >= _flushInterval)
                {
                    if (buffer.Count > 0)
                    {
                        await FlushAsync(buffer);
                        buffer.Clear();
                        lastFlush = now;
                    }
                }
                else
                {
                    await Task.Delay(_flushInterval, _cts.Token);
                }
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _log.LogWarning(ex, "drain loop iteration failed");
            }
        }

        if (buffer.Count > 0)
        {
            try { await FlushAsync(buffer); } catch { /* shutdown */ }
        }
    }

    private async Task FlushAsync(IReadOnlyList<EventPayload> batch)
    {
        try
        {
            using var resp = await _http.PostAsJsonAsync(_endpoint, batch, SerializerOptions, _cts.Token);
            if (!resp.IsSuccessStatusCode)
            {
                var body = await resp.Content.ReadAsStringAsync(_cts.Token);
                _log.LogWarning("events POST failed: {Status} {Body}", resp.StatusCode, body);
            }
        }
        catch (OperationCanceledException) when (_cts.IsCancellationRequested)
        {
            // shutdown in progress — drop silently
        }
        catch (Exception ex)
        {
            _log.LogWarning(ex, "events POST exception (dropped {Count} events)", batch.Count);
        }
    }

    public async ValueTask DisposeAsync()
    {
        _cts.Cancel();
        _channel.Writer.TryComplete();
        try { await _drainTask; } catch { /* shutdown */ }
        _http.Dispose();
        _cts.Dispose();
    }

    private static readonly JsonSerializerOptions SerializerOptions = new()
    {
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
    };

    private sealed record EventPayload(
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
        [property: JsonPropertyName("timestamp_ms")] long TimestampMs);
}
