using Microsoft.Extensions.Logging;

namespace GameSimulator;

public enum PlayerState
{
    InMenu,
    LoadingScene,
    PlayingLevel,
}

public sealed class VirtualPlayer
{
    private static readonly string[] Platforms = ["ios", "android", "pc", "console"];
    private static readonly Dictionary<string, string[]> DeviceModels = new()
    {
        ["ios"] = ["iphone_14", "iphone_15_pro", "ipad_air_5"],
        ["android"] = ["pixel_8", "galaxy_s24", "redmi_note_13", "oneplus_12"],
        ["pc"] = ["rtx_4070", "rtx_3060", "integrated_intel"],
        ["console"] = ["ps5", "xbox_series_x", "switch_2"],
    };
    private static readonly string[] GameVersions = ["1.4.1", "1.4.2", "1.5.0"];
    private static readonly string[] LevelIds =
        ["forest_1", "forest_2", "cavern_1", "cavern_2", "boss_1", "sky_1", "sky_2", "boss_2"];
    private static readonly string[] DeathReasons =
        ["enemy_melee", "enemy_projectile", "fall_damage", "trap", "timeout", "boss_special"];

    public string PlayerId { get; }
    public string SessionId { get; private set; }
    public string Platform { get; }
    public string DeviceModel { get; }
    public string GameVersion { get; }

    private readonly Random _rng;
    private readonly EventReporter _events;
    private readonly MetricsReporter _metrics;
    private readonly ILogger _log;

    private PlayerState _state = PlayerState.InMenu;
    private string _currentLevel = string.Empty;
    private string _currentScene = "main_menu";
    private DateTime _levelStartedAt;
    private DateTime _nextTransitionAt;
    private DateTime _lastMetricsAt = DateTime.MinValue;
    private long _sessionGold;
    private long _sessionScore;

    public VirtualPlayer(int seed, EventReporter events, MetricsReporter metrics, ILogger log)
    {
        _rng = new Random(seed);
        _events = events;
        _metrics = metrics;
        _log = log;

        PlayerId = $"player_{seed:x8}";
        SessionId = Guid.NewGuid().ToString("n");
        Platform = Platforms[_rng.Next(Platforms.Length)];
        DeviceModel = DeviceModels[Platform][_rng.Next(DeviceModels[Platform].Length)];
        GameVersion = GameVersions[_rng.Next(GameVersions.Length)];

        _nextTransitionAt = DateTime.UtcNow.AddSeconds(_rng.Next(2, 10));
    }

    public async Task TickAsync(DateTime now, CancellationToken ct)
    {
        if (now >= _nextTransitionAt)
        {
            await AdvanceStateAsync(now, ct);
        }

        if ((now - _lastMetricsAt).TotalSeconds >= 5)
        {
            ReportMetrics();
            _lastMetricsAt = now;
        }
    }

    private async Task AdvanceStateAsync(DateTime now, CancellationToken ct)
    {
        switch (_state)
        {
            case PlayerState.InMenu:
                _currentLevel = LevelIds[_rng.Next(LevelIds.Length)];
                _state = PlayerState.LoadingScene;
                _currentScene = $"loading_{_currentLevel}";
                _nextTransitionAt = now.AddSeconds(_rng.NextDouble() * 2 + 1);
                break;

            case PlayerState.LoadingScene:
                _state = PlayerState.PlayingLevel;
                _currentScene = _currentLevel;
                _levelStartedAt = now;
                _nextTransitionAt = now.AddSeconds(_rng.NextDouble() * 60 + 20);
                await _events.EnqueueAsync(new Events.LevelStarted(this, _currentLevel, now), ct);
                break;

            case PlayerState.PlayingLevel:
                var duration = (now - _levelStartedAt).TotalMilliseconds;
                var died = _rng.NextDouble() < 0.35;
                if (died)
                {
                    var reason = DeathReasons[_rng.Next(DeathReasons.Length)];
                    await _events.EnqueueAsync(
                        new Events.PlayerDeath(this, _currentLevel, duration, reason, now), ct);
                }
                else
                {
                    var gold = _rng.Next(10, 200);
                    var score = _rng.Next(500, 5000);
                    _sessionGold += gold;
                    _sessionScore += score;
                    await _events.EnqueueAsync(
                        new Events.LevelCompleted(this, _currentLevel, duration, score, gold, now), ct);
                }

                if (_rng.NextDouble() < 0.04)
                {
                    var amount = Math.Round(_rng.NextDouble() * 20 + 0.99, 2);
                    await _events.EnqueueAsync(new Events.IapPurchase(this, amount, now), ct);
                }

                if (_rng.NextDouble() < 0.08)
                {
                    await StartNewSessionAsync(now, ct);
                    return;
                }

                _state = PlayerState.InMenu;
                _currentScene = "main_menu";
                _currentLevel = string.Empty;
                _nextTransitionAt = now.AddSeconds(_rng.NextDouble() * 8 + 2);
                break;
        }
    }

    private Task StartNewSessionAsync(DateTime now, CancellationToken ct)
    {
        SessionId = Guid.NewGuid().ToString("n");
        _state = PlayerState.InMenu;
        _currentScene = "main_menu";
        _currentLevel = string.Empty;
        _sessionGold = 0;
        _sessionScore = 0;
        _nextTransitionAt = now.AddSeconds(_rng.NextDouble() * 15 + 5);
        _log.LogDebug("player {PlayerId} started new session {SessionId}", PlayerId, SessionId);
        return Task.CompletedTask;
    }

    private void ReportMetrics()
    {
        double baselineFps = Platform switch
        {
            "pc" => 120,
            "console" => 60,
            "ios" => 60,
            "android" => DeviceModel.StartsWith("redmi") ? 40 : 55,
            _ => 50,
        };
        double noiseFps = (_rng.NextDouble() - 0.5) * 10;
        double fps = Math.Max(15, baselineFps + noiseFps - (_state == PlayerState.PlayingLevel ? 0 : 2));
        double frameTimeMs = 1000.0 / fps;

        double baselineMem = Platform switch
        {
            "pc" => 1200,
            "console" => 1800,
            "ios" => 450,
            "android" => 520,
            _ => 600,
        };
        double memMb = baselineMem + _rng.NextDouble() * 200;

        long drawCalls = _state == PlayerState.PlayingLevel
            ? _rng.Next(800, 2200)
            : _rng.Next(80, 300);

        _metrics.Report(this, _currentScene, fps, frameTimeMs, memMb, drawCalls);
    }
}
