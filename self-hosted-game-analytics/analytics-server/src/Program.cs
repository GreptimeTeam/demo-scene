using AnalyticsServer.Endpoints;
using AnalyticsServer.Storage;
using GreptimeDB.Ingester.DependencyInjection;

var builder = WebApplication.CreateBuilder(args);

var greptimeEndpoint = Environment.GetEnvironmentVariable("GREPTIMEDB_ENDPOINT")
    ?? "http://greptimedb:4001";
var greptimeDb = Environment.GetEnvironmentVariable("GREPTIMEDB_DATABASE") ?? "public";

builder.Services.AddGreptimeClient(options =>
{
    options.Endpoint = greptimeEndpoint;
    options.Database = greptimeDb;
    options.WriteTimeout = TimeSpan.FromSeconds(30);
});

builder.Services.AddSingleton<IGreptimeEventsWriter, GreptimeEventsWriter>();

var app = builder.Build();

app.MapGet("/healthz", () => Results.Ok(new { status = "ok" }));
app.MapEvents();

app.Logger.LogInformation(
    "Analytics server starting, writing to GreptimeDB at {Endpoint}, db={Db}",
    greptimeEndpoint, greptimeDb);

app.Run();
