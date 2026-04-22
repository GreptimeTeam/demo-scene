using AnalyticsServer.Models;
using AnalyticsServer.Storage;

namespace AnalyticsServer.Endpoints;

public static class EventsEndpoint
{
    public static IEndpointRouteBuilder MapEvents(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/events", async (
            GameEvent[] batch,
            IGreptimeEventsWriter writer,
            CancellationToken ct) =>
        {
            if (batch is null || batch.Length == 0)
            {
                return Results.BadRequest(new { error = "empty batch" });
            }

            var affected = await writer.WriteBatchAsync(batch, ct);
            return Results.Ok(new { accepted = batch.Length, affected });
        });

        app.MapPost("/api/events/single", async (
            GameEvent evt,
            IGreptimeEventsWriter writer,
            CancellationToken ct) =>
        {
            var affected = await writer.WriteBatchAsync(new[] { evt }, ct);
            return Results.Ok(new { affected });
        });

        return app;
    }
}
