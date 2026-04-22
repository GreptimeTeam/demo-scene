using System.Diagnostics;
using System.Diagnostics.Metrics;
using OpenTelemetry;
using OpenTelemetry.Exporter;
using OpenTelemetry.Metrics;
using OpenTelemetry.Resources;

namespace GameSimulator;

public sealed class MetricsReporter : IDisposable
{
    public const string MeterName = "com.greptime.game-analytics-demo";

    private readonly Meter _meter;
    private readonly MeterProvider _provider;
    private readonly Gauge<double> _fps;
    private readonly Histogram<double> _frameTime;
    private readonly Gauge<double> _memoryMb;
    private readonly Gauge<long> _drawCalls;

    public MetricsReporter(string otlpEndpoint)
    {
        _meter = new Meter(MeterName, "1.0");
        // Keep instrument units empty so the OTLP -> Prometheus naming stays
        // predictable (no unit suffix appended). Metrics surface in GreptimeDB
        // as: game_fps, game_frame_time_{bucket,count,sum}, game_memory, game_draw_calls.
        _fps = _meter.CreateGauge<double>("game.fps");
        _frameTime = _meter.CreateHistogram<double>("game.frame_time");
        _memoryMb = _meter.CreateGauge<double>("game.memory");
        _drawCalls = _meter.CreateGauge<long>("game.draw_calls");

        _provider = Sdk.CreateMeterProviderBuilder()
            .SetResourceBuilder(ResourceBuilder.CreateDefault()
                .AddService("game-simulator", serviceVersion: "1.0.0"))
            .AddMeter(MeterName)
            .AddOtlpExporter(opt =>
            {
                opt.Endpoint = new Uri(otlpEndpoint);
                opt.Protocol = OtlpExportProtocol.HttpProtobuf;
                opt.ExportProcessorType = ExportProcessorType.Batch;
            })
            .Build()!;
    }

    public void Report(VirtualPlayer player, string scene, double fps, double frameTimeMs, double memMb, long drawCalls)
    {
        var tags = new TagList
        {
            { "player_id", player.PlayerId },
            { "platform", player.Platform },
            { "device_model", player.DeviceModel },
            { "scene_name", scene },
            { "game_version", player.GameVersion },
            { "session_id", player.SessionId },
        };

        _fps.Record(fps, tags);
        _frameTime.Record(frameTimeMs, tags);
        _memoryMb.Record(memMb, tags);
        _drawCalls.Record(drawCalls, tags);
    }

    public void Dispose()
    {
        _provider.Dispose();
        _meter.Dispose();
    }
}
