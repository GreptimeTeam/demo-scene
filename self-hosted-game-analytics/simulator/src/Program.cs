using GameSimulator;
using Microsoft.Extensions.Logging;

var playerCount = int.Parse(Environment.GetEnvironmentVariable("SIM_PLAYER_COUNT") ?? "50");
var analyticsUrl = Environment.GetEnvironmentVariable("ANALYTICS_URL")
    ?? "http://analytics-server:8080";
var otlpEndpoint = Environment.GetEnvironmentVariable("OTEL_EXPORTER_OTLP_METRICS_ENDPOINT")
    ?? "http://greptimedb:4000/v1/otlp/v1/metrics";
var tickMs = int.Parse(Environment.GetEnvironmentVariable("SIM_TICK_MS") ?? "250");

using var loggerFactory = LoggerFactory.Create(b => b
    .AddSimpleConsole(o =>
    {
        o.SingleLine = true;
        o.TimestampFormat = "HH:mm:ss ";
    })
    .SetMinimumLevel(LogLevel.Information));

var log = loggerFactory.CreateLogger("Simulator");

log.LogInformation(
    "starting simulator: players={Players}, analytics={Analytics}, otlp={Otlp}",
    playerCount, analyticsUrl, otlpEndpoint);

using var cts = new CancellationTokenSource();
Console.CancelKeyPress += (_, e) =>
{
    e.Cancel = true;
    cts.Cancel();
};

await using var events = new EventReporter(analyticsUrl, loggerFactory.CreateLogger<EventReporter>());
using var metrics = new MetricsReporter(otlpEndpoint);

var players = new VirtualPlayer[playerCount];
for (int i = 0; i < playerCount; i++)
{
    players[i] = new VirtualPlayer(
        seed: Random.Shared.Next(),
        events: events,
        metrics: metrics,
        log: loggerFactory.CreateLogger<VirtualPlayer>());
}

log.LogInformation("spawned {Count} virtual players", playerCount);

var tickDelay = TimeSpan.FromMilliseconds(tickMs);
var statsInterval = TimeSpan.FromSeconds(30);
var lastStats = DateTime.UtcNow;
long ticksTotal = 0;

while (!cts.IsCancellationRequested)
{
    var now = DateTime.UtcNow;
    var tasks = new Task[players.Length];
    for (int i = 0; i < players.Length; i++)
    {
        tasks[i] = players[i].TickAsync(now, cts.Token);
    }
    try
    {
        await Task.WhenAll(tasks);
    }
    catch (OperationCanceledException) { break; }

    ticksTotal++;

    if (now - lastStats >= statsInterval)
    {
        log.LogInformation("heartbeat: ticks={Ticks}, players={Players}", ticksTotal, playerCount);
        lastStats = now;
    }

    try { await Task.Delay(tickDelay, cts.Token); }
    catch (OperationCanceledException) { break; }
}

log.LogInformation("shutting down");
