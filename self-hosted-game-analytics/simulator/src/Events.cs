namespace GameSimulator;

public static class Events
{
    public interface IGameEvent
    {
        string EventType { get; }
        VirtualPlayer Player { get; }
        DateTime Timestamp { get; }
        string? LevelId { get; }
        double? DurationMs { get; }
        long? Score { get; }
        long? GoldDelta { get; }
        double? AmountUsd { get; }
        string? Reason { get; }
    }

    public sealed record LevelStarted(VirtualPlayer Player, string Level, DateTime Timestamp) : IGameEvent
    {
        public string EventType => "level_started";
        public string? LevelId => Level;
        public double? DurationMs => null;
        public long? Score => null;
        public long? GoldDelta => null;
        public double? AmountUsd => null;
        public string? Reason => null;
    }

    public sealed record LevelCompleted(
        VirtualPlayer Player,
        string Level,
        double Duration,
        long ScoreValue,
        long Gold,
        DateTime Timestamp) : IGameEvent
    {
        public string EventType => "level_completed";
        public string? LevelId => Level;
        public double? DurationMs => Duration;
        public long? Score => ScoreValue;
        public long? GoldDelta => Gold;
        public double? AmountUsd => null;
        public string? Reason => null;
    }

    public sealed record PlayerDeath(
        VirtualPlayer Player,
        string Level,
        double Duration,
        string DeathReason,
        DateTime Timestamp) : IGameEvent
    {
        public string EventType => "player_death";
        public string? LevelId => Level;
        public double? DurationMs => Duration;
        public long? Score => null;
        public long? GoldDelta => null;
        public double? AmountUsd => null;
        public string? Reason => DeathReason;
    }

    public sealed record IapPurchase(VirtualPlayer Player, double UsdAmount, DateTime Timestamp) : IGameEvent
    {
        public string EventType => "iap_purchase";
        public string? LevelId => null;
        public double? DurationMs => null;
        public long? Score => null;
        public long? GoldDelta => null;
        public double? AmountUsd => UsdAmount;
        public string? Reason => null;
    }
}
