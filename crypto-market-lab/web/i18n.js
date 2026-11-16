const chinese = {
  "{seconds}s since last trade": "距最近成交 {seconds} 秒",
  "Loading…": "加载中…",
  "INTERVAL": "时长",
  "1 minute": "1 分钟",
  "5 minutes": "5 分钟",
  "Stop": "停止",
  "Market": "交易对",
  "Market time series": "行情时间序列",
  "BUY": "主动买入",
  "SELL": "主动卖出",
  "BID": "买一",
  "ASK": "卖一",
  "{seconds}s since last received quote": "距最近报价接收 {seconds} 秒",
  "Waiting for live quote samples.": "等待实时报价采样。",
  "Request failed": "请求失败",
  "No archive imported for this market": "该交易对尚未导入历史数据",
  "Loading minute…": "正在加载分钟明细…",
  "LOADING": "加载中",
  "RUNNING": "回放中",
  "STOPPING": "正在停止",
  "STOPPED": "已停止",
  "COMPLETE": "已完成",
  "FAILED": "失败",
  "cursor": "回放时间",
  "Select a UTC start minute": "请选择 UTC 开始时间（精确到分钟）",
  "EXACT RESULTS MATCH": "结果完全一致",
  "RESULT MISMATCH": "结果不一致",
  "GreptimeDB query failed; see desk logs": "GreptimeDB 查询失败，详情见工作台服务日志",
  "No historical trades imported": "尚未导入历史成交",
  "Import an archive before running the comparison": "请先导入历史归档，再运行查询对照",
  "Start a replay for this symbol first": "请先为该交易对启动回放",
  "A replay is already active; stop it before starting another": "已有回放正在运行，请先停止当前回放",
  "No archived trades in the selected interval": "所选区间没有历史归档成交",
  "Interval exceeds 100,000 trades; select one minute": "所选区间超过 10 万笔成交，请选择 1 分钟",
  "Invalid symbol or mode": "交易对或模式无效",
  "Select a UTC minute": "请选择 UTC 分钟",
  "No replay for this symbol": "该交易对没有回放",
  "Cross-origin writes are not allowed": "不允许跨来源写入",
  "Expected application/json": "请求类型必须为 application/json",
  "Invalid request size": "请求大小无效",
  "Expected a JSON object": "请求内容必须为 JSON 对象",
  "Select BTCUSDT or ETHUSDT and a 1- or 5-minute interval": "请选择 BTCUSDT 或 ETHUSDT，时长为 1 或 5 分钟",
  "Speed must be 1, 10, or 100": "倍速必须为 1、10 或 100",
  "Start must be aligned to a UTC minute": "开始时间必须对齐 UTC 分钟",
  "Unknown endpoint": "接口不存在",
  "Failed to fetch": "网络请求失败",
  "Replay failed; see desk logs": "回放失败，详情见工作台服务日志",
  "Market replay": "行情回放",
  "Archive": "历史",
  "Live": "实时",
  "Replay": "回放",
  "SQL inspector": "SQL 检查",
  "BINANCE · SPOT": "BINANCE · 现货",
  "Volume": "成交额",
  "Taker delta": "主动买卖差",
  "Trades": "成交笔数",
  "Candles": "K 线",
  "Trade bubbles": "成交气泡",
  "1 second": "1 秒",
  "Fit": "全览",
  "Volume at price": "按价位成交量",
  "Executed · not resting orders": "已成交量，非挂单深度",
  "Scroll to zoom · click to inspect": "滚轮缩放 · 点击查看成交",
  "Load an interval to replay": "加载区间后开始回放",
  "Space: play / pause · →: next trade": "空格：播放 / 暂停 · →：下一笔",
  "Start · UTC": "开始时间 · UTC",
  "Load replay": "加载回放",
  "Best quote": "最优报价",
  "Time & sales": "逐笔成交",
  "Price": "价格",
  "Size": "数量",
  "Time UTC": "时间 UTC",
  "Aggressive buy": "主动买入",
  "Aggressive sell": "主动卖出",
  "Cumulative delta": "累计主动买卖差",
  "Selected minute": "所选分钟",
  "SQL / Flow": "SQL / Flow",
  "Buy − sell base volume · resets at window start": "主动买量 − 主动卖量，窗口起点归零",
  "Click a candle or a trade to inspect its minute.": "点击 K 线或逐笔成交，查看所在分钟的明细。",
  "Trade ID": "成交 ID",
  "Side": "方向",
  "Compare full archive day": "对比完整归档日",
  "Exact results · raw events versus minute aggregates": "核对结果：原始成交与分钟聚合",
  "Current chart SQL": "当前图表 SQL",
  "Public trades · no simulated fills": "公开成交 · 不模拟订单撮合",
  "Pause": "暂停",
  "Play": "播放",
  "Next trade": "下一笔成交",
  "Chart interval": "图表周期",
  "Replay speed": "回放倍速",
  "Replay duration": "回放时长",
  "Play / pause": "播放 / 暂停",
  "Zoom out": "缩小",
  "Zoom in": "放大",
  "Waiting for the next trade": "等待下一笔成交",
  "Latest {count} prints · size = volume": "最近 {count} 笔 · 气泡大小表示成交量",
  "in window": "区间内",
  "REPLAY": "回放",
  "LIVE": "实时",
  "ARCHIVE": "历史",
  "Trades-only archive. Historical quotes are not available.": "归档仅含成交，没有历史报价。",
  "Latest {count}": "最近 {count} 笔",
  "Refresh failed": "刷新失败",
  "archive available": "有历史归档",
  "Largest 25 trades in this minute": "该分钟金额最大的 25 笔成交",
  "Replay is still stopping": "回放仍在停止，请稍后重试",
  "Running three alternating trials…": "交替运行两条查询，各三次…",
  "Raw": "原始查询",
  "3-trial median · HTTP · local cache": "3 次中位数 · HTTP · 本机缓存",
  "Full archive day · raw SQL": "完整归档日 · 原始 SQL",
  "PAUSED": "已暂停",
  "Speed changes require a running or paused replay": "仅在回放中或暂停时可调整倍速",
  "Pause requires a running replay": "仅在回放中可暂停",
  "Play requires a paused replay": "请先加载或暂停回放",
  "Step requires a paused replay": "逐笔推进需要先暂停",
  "Unknown replay action": "未知回放操作",
  "Invalid chart resolution": "无效的图表周期",
  "Invalid paused flag": "无效的暂停参数"
};
const languageParams = new URLSearchParams(location.search);
const requestedLanguage = languageParams.get('lang');
let savedLanguage;
try { savedLanguage = localStorage.getItem('crypto-desk-language'); } catch { /* Browser storage may be disabled. */ }
const language = ['en', 'zh-CN'].includes(requestedLanguage) ? requestedLanguage
  : ['en', 'zh-CN'].includes(savedLanguage) ? savedLanguage
  : navigator.language.toLowerCase().startsWith('zh') ? 'zh-CN' : 'en';
function t(message, values = {}) {
  const template = language === 'zh-CN' ? (chinese[message] || message) : message;
  return template.replace(/\{(\w+)\}/g, (match, key) => values[key] ?? match);
}
document.documentElement.lang = language;
document.title = t('Market replay') + ' · GreptimeDB';
document.querySelectorAll('[data-i18n]').forEach(element => {
  element.textContent = t(element.dataset.i18n);
});
document.querySelectorAll('[aria-label], [title]').forEach(element => {
  for (const attribute of ['aria-label', 'title']) {
    if (element.hasAttribute(attribute)) element.setAttribute(attribute, t(element.getAttribute(attribute)));
  }
});
document.getElementById('language').value = language;
document.getElementById('language').onchange = event => {
  const next = event.target.value;
  try { localStorage.setItem('crypto-desk-language', next); } catch { /* The URL also retains the language. */ }
  const url = new URL(location.href);
  url.searchParams.set('lang', next);
  url.searchParams.set('symbol', document.getElementById('symbol').value);
  location.assign(url.href);
};
