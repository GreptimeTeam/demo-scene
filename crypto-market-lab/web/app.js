const $ = id => document.getElementById(id);
const fmt = (value, digits = 2) => Number(value).toLocaleString(language, {minimumFractionDigits: digits, maximumFractionDigits: digits});
const compact = value => Intl.NumberFormat(language, {notation: 'compact', maximumFractionDigits: 2}).format(value);
const utc = value => new Date(value / 1000).toISOString().slice(11, 23);
const svg = (content, width = 900, height = 400) => `<svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" role="img" aria-label="${t('Market time series')}">${content}</svg>`;
const TICK_STEPS = [1e4, 5e4, 1e5, 2.5e5, 5e5, 1e6, 5e6, 1e7, 15e6, 30e6, 60e6, 120e6, 300e6, 600e6, 900e6, 1800e6, 3600e6];
const active = job => ['loading', 'running', 'paused', 'stopping'].includes(job.status);
let mode = ['live', 'history', 'replay'].includes(languageParams.get('mode')) ? languageParams.get('mode') : 'history';
let job = {status: 'idle'}, data = null, chartType = 'candles', zoom = 1, selected = null;
let busy = false, pending = false, timer, inspecting = 0, chartDomain = null, loadingReplay = false, generation = 0;
let previousIds = new Set();
const initialSymbol = languageParams.get('symbol');
if (['BTCUSDT', 'ETHUSDT'].includes(initialSymbol)) $('symbol').value = initialSymbol;

async function api(path, body) {
  const response = await fetch(path, body === undefined ? {} : {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
  });
  const result = await response.json();
  if (!response.ok) throw Error(t(result.error || 'Request failed'));
  return result;
}
function showError(error) {
  $('error').hidden = false;
  $('error').textContent = t(error.message);
}
function setMode(next) {
  mode = next; selected = null; zoom = 1; previousIds.clear();
  generation++; inspecting++; data = null; chartDomain = null;
  for (const id of ['chart', 'tape', 'profile', 'flow-chart', 'minute-trades', 'selection-label']) $(id).textContent = '';
  for (const id of ['last-price', 'change', 'volume', 'delta', 'count', 'flow-value', 'spread', 'event-clock']) $(id).textContent = '—';
  $('book').textContent = t('Loading…');
  $('status').textContent = t('Loading…');
  $('chart-tooltip').hidden = true;
  $('minute-prompt').hidden = false;
  $('minute-prompt').textContent = t('Click a candle or a trade to inspect its minute.');
  const url = new URL(location.href); url.searchParams.set('mode', mode);
  window.history.replaceState(null, '', url.href);
  $('history-mode').classList.toggle('selected', mode === 'history');
  $('live-mode').classList.toggle('selected', mode === 'live');
  $('replay-mode').classList.toggle('selected', mode === 'replay');
  $('resolution').value = mode === 'replay' ? '1 second' : '1 minute';
  refresh();
}
function panel(name) {
  for (const id of ['flow', 'trades', 'query']) {
    $(id + '-panel').hidden = id !== name;
    $(id + '-tab').classList.toggle('selected', id === name);
  }
}
function renderPlayer() {
  const state = job.status;
  $('play').disabled = !['running', 'paused'].includes(state);
  $('play').textContent = state === 'running' ? 'Ⅱ' : '▶';
  $('play').setAttribute('aria-label', t(state === 'running' ? 'Pause' : 'Play'));
  $('step').disabled = state !== 'paused';
  $('replay-mode').disabled = !job.symbol;
  $('stop').disabled = !active(job) || state === 'stopping';
  $('load').disabled = loadingReplay || ['loading', 'stopping'].includes(state);
  $('replay-state').textContent = state === 'idle' ? t('Load an interval to replay') : `${t(state.toUpperCase())} · ${job.symbol} · ${job.speed}×`;
  $('replay-count').textContent = job.total ? `${fmt(job.written, 0)} / ${fmt(job.total, 0)}` : '';
  $('progress').max = job.total || 1; $('progress').value = job.written || 0;
  if (job.error) showError(Error(job.error));
}
function drawChart() {
  if (!data) return;
  const bubbleRange = chartType === 'bubbles' && data.tape.length;
  const unit = bubbleRange ? Math.max(1000, (data.tape[0][0] - data.tape.at(-1)[0]) / 60)
    : data.resolution === '1 second' ? 1e6 : 60e6;
  const rangeStart = bubbleRange ? Math.max(data.start, data.tape.at(-1)[0] - unit) : data.start;
  const end = bubbleRange ? Math.min(data.end, data.tape[0][0] + unit)
    : mode === 'replay' ? Math.min(data.end, (data.replay?.cursor || data.start) + unit) : data.end;
  const span = Math.max(unit * 8, (end - rangeStart) / zoom);
  const start = Math.max(rangeStart, end - span);
  const bars = data.candles.filter(row => row[0] >= start && row[0] <= end);
  const prints = data.tape.filter(row => row[0] >= start && row[0] <= end);
  const points = chartType === 'bubbles' ? prints.map(row => +row[1]) : bars.flatMap(row => [+row[2], +row[3]]);
  if (!points.length) {
    chartDomain = null;
    $('chart').innerHTML = `<div class="chart-empty">${t('Waiting for the next trade')}</div>`;
    $('chart-info').textContent = ''; return;
  }
  const width = 900, right = 820, top = 20, bottom = 282;
  let low = Math.min(...points), high = Math.max(...points);
  const padding = Math.max((high - low) * .12, high * .00002);
  low -= padding; high += padding;
  const x = time => 12 + (time - start) / Math.max(unit, end - start) * (right - 12);
  const y = price => top + (high - price) / (high - low) * (bottom - top);
  chartDomain = {start, end, low, high, right, top, bottom, bars};
  const last = +data.latest[0]?.[0];
  let content = '';
  for (let i = 0; i < 5; i++) {
    const price = high - (high - low) * i / 4, py = y(price);
    content += `<line x1="0" x2="${right}" y1="${py}" y2="${py}" stroke="#edf0f3"/>`;
    // The last-price tag is drawn on the same axis; skip the tick label it would cover.
    if (!(Math.abs(y(last) - py) < 14)) content += `<text x="${right + 12}" y="${py + 4}" font-size="10" fill="#7a818b">${fmt(price)}</text>`;
  }
  const tickStep = TICK_STEPS.find(step => (end - start) / step <= 6) ?? TICK_STEPS.at(-1);
  for (let time = Math.ceil(start / tickStep) * tickStep; time <= end; time += tickStep) {
    const px = x(time);
    content += `<line x1="${px}" x2="${px}" y1="0" y2="370" stroke="#f2f3f5"/><text x="${px}" y="393" text-anchor="${px < 40 ? 'start' : 'middle'}" font-size="9" fill="#7a818b">${utc(time).slice(0, tickStep < 1e6 ? 12 : tickStep < 60e6 ? 8 : 5)}</text>`;
  }
  if (chartType === 'candles') {
    const candleWidth = Math.max(1, Math.min(22, (right - 12) * unit / (end - start) * .65));
    const volumeMax = Math.max(...bars.map(row => +row[5]), 1);
    for (const row of bars) {
      const px = x(row[0] + unit / 2), color = +row[4] >= +row[1] ? '#218574' : '#cb5960';
      const buys = +row[6] / volumeMax * 63, sells = (+row[5] - row[6]) / volumeMax * 63;
      content += `<g><line x1="${px}" x2="${px}" y1="${y(row[2])}" y2="${y(row[3])}" stroke="${color}"/><rect x="${px - candleWidth / 2}" y="${Math.min(y(row[1]), y(row[4]))}" width="${candleWidth}" height="${Math.max(1, Math.abs(y(row[1]) - y(row[4])))}" fill="${color}"/><rect x="${px - candleWidth / 2}" y="${370 - buys}" width="${candleWidth}" height="${buys}" fill="#218574" opacity=".5"/><rect x="${px - candleWidth / 2}" y="${370 - buys - sells}" width="${candleWidth}" height="${sells}" fill="#cb5960" opacity=".5"/></g>`;
    }
  } else {
    const chronological = [...prints].reverse(), maxSize = Math.max(...prints.map(row => +row[2]), 1e-12);
    content += `<polyline points="${chronological.map(row => `${x(row[0])},${y(row[1])}`).join(' ')}" fill="none" stroke="#bbc4cf" stroke-width="1"/>`;
    for (const row of chronological) {
      const color = row[4] ? '#218574' : '#cb5960', radius = 2 + Math.sqrt(+row[2] / maxSize) * 12;
      content += `<circle cx="${x(row[0])}" cy="${y(row[1])}" r="${radius}" fill="${color}" fill-opacity=".32" stroke="${color}" stroke-width=".7"><title>${utc(row[0])} · ${fmt(row[1])} · ${fmt(row[2], 5)} · ${t(row[4] ? 'BUY' : 'SELL')}</title></circle>`;
    }
  }
  if (selected && selected >= start && selected <= end) content += `<line x1="${x(selected)}" x2="${x(selected)}" y1="0" y2="370" stroke="#315da8" stroke-dasharray="4 3"/>`;
  if (Number.isFinite(last) && last >= low && last <= high) content += `<line x1="0" x2="${right}" y1="${y(last)}" y2="${y(last)}" stroke="#8c98a7" stroke-dasharray="2 3"/><rect x="${right}" y="${y(last) - 9}" width="80" height="18" fill="#364455"/><text x="${right + 7}" y="${y(last) + 3}" fill="#fff" font-size="10">${fmt(last)}</text>`;
  if (mode === 'replay') {
    const cursor = x(data.replay.cursor);
    content += `<line x1="${cursor}" x2="${cursor}" y1="0" y2="370" stroke="#bd8752" stroke-dasharray="3 3"/>`;
  }
  content += '<g id="crosshair" visibility="hidden"><line id="cross-x" y1="0" y2="370" stroke="#a0a9b4" stroke-dasharray="2 3"/><line id="cross-y" x1="0" x2="820" stroke="#a0a9b4" stroke-dasharray="2 3"/></g>';
  $('chart').innerHTML = svg(content, width, 400);
  $('chart-info').textContent = chartType === 'bubbles' ? t('Latest {count} prints · size = volume', {count: prints.length}) : `${t(data.resolution)} · ${bars.length}`;
}
function drawFlow() {
  const rows = data.candles;
  let cumulative = 0;
  const values = rows.map(row => { cumulative += 2 * Number(row[6]) - Number(row[5]); return [row[0], cumulative]; });
  $('flow-value').textContent = `${cumulative >= 0 ? '+' : ''}${fmt(cumulative, 3)}`;
  $('flow-value').className = cumulative >= 0 ? 'buy' : 'sell';
  if (!values.length) { $('flow-chart').innerHTML = ''; return; }
  const extent = Math.max(...values.map(row => Math.abs(row[1])), .001);
  const end = Math.max(values.at(-1)[0], values[0][0] + 1);
  const points = values.map(row => `${(row[0] - values[0][0]) / (end - values[0][0]) * 800},${55 - row[1] / extent * 43}`).join(' ');
  $('flow-chart').innerHTML = svg(`<line x1="0" x2="800" y1="55" y2="55" stroke="#e1e5eb"/><polyline points="${points}" fill="none" stroke="${cumulative >= 0 ? '#218574' : '#cb5960'}" stroke-width="1.5"/>`, 800, 110);
}
function render(next) {
  data = next;
  if (next.replay) { job = next.replay; renderPlayer(); }
  const summary = next.summary, volume = +summary[1] || 0, delta = 2 * (+summary[3] || 0) - volume;
  $('last-price').textContent = next.latest.length ? fmt(next.latest[0][0]) : '—';
  const first = +next.candles[0]?.[1], last = +next.latest[0]?.[0], change = first ? (last / first - 1) * 100 : null;
  $('change').textContent = change === null ? '—' : `${change >= 0 ? '+' : ''}${fmt(change)}% ${t('in window')}`;
  $('change').className = change >= 0 ? 'buy' : 'sell';
  $('volume').textContent = compact(summary[2] || 0) + ' USDT';
  $('delta').textContent = (delta >= 0 ? '+' : '') + fmt(delta, 3) + ' ' + next.symbol.slice(0, -4);
  $('delta').className = delta >= 0 ? 'buy' : 'sell';
  $('count').textContent = fmt(summary[0], 0);
  $('mode-label').textContent = t(mode === 'replay' ? 'REPLAY' : mode === 'live' ? 'LIVE' : 'ARCHIVE');
  $('mode-label').classList.toggle('replaying', mode === 'replay');
  const clock = next.replay?.cursor || summary[4] || next.start;
  $('event-clock').textContent = utc(clock).slice(0, 8) + ' UTC';
  $('status').textContent = new Date(clock / 1000).toISOString().slice(0, 10)
    + (mode === 'live' && summary[4] ? ' · ' + t('{seconds}s since last trade', {seconds: fmt((next.now - summary[4]) / 1e6, 1)}) : '');
  $('dataset').textContent = next.dataset;
  $('chart-range').textContent = `${utc(next.start).slice(0, 8)} — ${utc(next.end).slice(0, 8)} UTC`;
  const quote = next.quotes.at(-1);
  if (quote) {
    const spread = (+quote[3] - quote[1]) / ((+quote[3] + +quote[1]) / 2) * 10000;
    $('spread').textContent = fmt(spread, 3) + ' bps';
    $('book').innerHTML = `<div class="book-row buy"><span>${t('BID')}</span><span>${fmt(quote[1])}</span><span>${fmt(quote[2], 4)}</span></div><div class="book-row sell"><span>${t('ASK')}</span><span>${fmt(quote[3])}</span><span>${fmt(quote[4], 4)}</span></div><small>${t('{seconds}s since last received quote', {seconds: fmt((next.now - quote[5]) / 1e6, 1)})}</small>`;
  } else {
    $('spread').textContent = '—';
    $('book').textContent = t(mode === 'live' ? 'Waiting for live quote samples.' : 'Trades-only archive. Historical quotes are not available.');
  }
  const maxSize = Math.max(...next.tape.map(row => +row[2]), 1e-12);
  $('tape').innerHTML = next.tape.slice(0, 80).map(row => `<button class="tape-row ${row[4] ? 'buy' : 'sell'} ${previousIds.size && !previousIds.has(row[5]) ? 'new' : ''} ${+row[2] >= maxSize * .5 ? 'large' : ''}" data-time="${row[0]}" title="${t(row[4] ? 'BUY' : 'SELL')} · ${row[5]}"><span>${fmt(row[1])}</span><span>${fmt(row[2], 5)}</span><span>${utc(row[0]).slice(0, 8)}</span></button>`).join('');
  previousIds = new Set(next.tape.map(row => row[5]));
  $('tape-note').textContent = t('Latest {count}', {count: Math.min(80, next.tape.length)});
  const maxVolume = Math.max(...next.profile.map(row => +row[1] + +row[2]), 1e-12);
  $('profile').innerHTML = next.profile.map(row => `<div class="profile-row" title="${fmt(row[0], 3)}–${fmt(row[0] + next.profile_step, 3)} · ${fmt(+row[1] + +row[2], 5)}"><span>${fmt(row[0], 1)}</span><div class="profile-bars"><i class="buy" style="width:${+row[1] / maxVolume * 100}%"></i><i class="sell" style="width:${+row[2] / maxVolume * 100}%"></i></div></div>`).join('');
  if (!$('benchmark').disabled && !$('raw-sql').dataset.comparison) $('raw-sql').textContent = next.candle_sql;
  drawChart(); drawFlow();
}
async function refresh() {
  clearTimeout(timer);
  if (busy) { pending = true; return; }
  busy = true;
  const symbol = $('symbol').value, requestedMode = mode, resolution = $('resolution').value, requestedGeneration = generation;
  const started = performance.now();
  try {
    const result = await api(`/api/desk?symbol=${symbol}&mode=${requestedMode}&resolution=${encodeURIComponent(resolution)}`);
    if (requestedGeneration === generation && symbol === $('symbol').value && requestedMode === mode && resolution === $('resolution').value) {
      render(result); $('error').hidden = true;
      $('request-time').textContent = `${fmt(performance.now() - started, 0)} ms · HTTP`;
    }
  } catch (error) { if (requestedGeneration === generation) { showError(error); $('status').textContent = t('Refresh failed'); } }
  finally {
    busy = false;
    if (pending) { pending = false; refresh(); }
    else timer = setTimeout(refresh, mode === 'replay' && job.status === 'running' ? 300 : mode === 'live' ? 2000 : 5000);
  }
}
async function catalog() {
  const symbol = $('symbol').value;
  try {
    const [[first, last]] = await api('/api/catalog?symbol=' + symbol);
    if (symbol !== $('symbol').value) return;
    if (first === null) throw Error(t('No archive imported for this market'));
    const iso = value => new Date(value / 1000).toISOString().slice(0, 16);
    $('replay-start').min = iso(first); $('replay-start').max = iso(last);
    $('replay-start').value = iso(first);
    $('available').textContent = new Date(first / 1000).toISOString().slice(0, 10) + ' · ' + t('archive available');
  } catch (error) { $('available').textContent = t(error.message); }
}
async function inspect(time) {
  selected = time; drawChart(); panel('trades');
  const minute = Math.floor(time / 60e6) * 60e6, id = ++inspecting, symbol = $('symbol').value;
  $('selection-label').textContent = utc(time) + ' UTC';
  $('minute-prompt').hidden = false; $('minute-prompt').textContent = t('Loading minute…');
  $('minute-trades').textContent = '';
  try {
    const result = await api(`/api/minute?symbol=${symbol}&mode=${mode}&start=${minute}`);
    if (id !== inspecting || symbol !== $('symbol').value) return;
    $('minute-prompt').textContent = t('Largest 25 trades in this minute');
    $('minute-trades').innerHTML = result.rows.map(row => `<tr><td>${utc(row[0])}</td><td>${row[1]}</td><td class="${row[5] ? 'buy' : 'sell'}">${t(row[5] ? 'BUY' : 'SELL')}</td><td>${fmt(row[2])}</td><td>${fmt(row[3], 5)}</td><td>${fmt(row[4])}</td></tr>`).join('');
    if (mode !== 'live') $('replay-start').value = new Date(minute / 1000).toISOString().slice(0, 16);
  } catch (error) { $('minute-prompt').textContent = t(error.message); }
}
function chartPoint(event) {
  if (!chartDomain) return null;
  const rect = $('chart').getBoundingClientRect();
  const x = (event.clientX - rect.left) / rect.width * 900, y = (event.clientY - rect.top) / rect.height * 400;
  if (x < 12 || x > chartDomain.right) return null;
  return {x, y, time: chartDomain.start + (x - 12) / (chartDomain.right - 12) * (chartDomain.end - chartDomain.start)};
}
$('chart').addEventListener('pointermove', event => {
  const point = chartPoint(event); if (!point) return;
  $('crosshair')?.setAttribute('visibility', 'visible');
  for (const key of ['x1', 'x2']) $('cross-x')?.setAttribute(key, point.x);
  for (const key of ['y1', 'y2']) $('cross-y')?.setAttribute(key, point.y);
  const price = chartDomain.high - (point.y - chartDomain.top) / (chartDomain.bottom - chartDomain.top) * (chartDomain.high - chartDomain.low);
  $('chart-tooltip').hidden = false;
  $('chart-tooltip').textContent = `${utc(point.time)} UTC · ${fmt(price)}`;
});
$('chart').addEventListener('pointerleave', () => { $('crosshair')?.setAttribute('visibility', 'hidden'); $('chart-tooltip').hidden = true; });
$('chart').addEventListener('click', event => { const point = chartPoint(event); if (point) inspect(point.time); });
$('chart').addEventListener('wheel', event => { event.preventDefault(); zoom = Math.max(1, Math.min(16, zoom * (event.deltaY < 0 ? 1.3 : 1 / 1.3))); drawChart(); }, {passive: false});
$('tape').addEventListener('click', event => { const row = event.target.closest('[data-time]'); if (row) inspect(Number(row.dataset.time)); });
async function control(action, speed) {
  try { job = await api('/api/replay/control', {action, speed}); renderPlayer(); refresh(); }
  catch (error) { showError(error); }
}
$('play').onclick = () => control(job.status === 'running' ? 'pause' : 'play');
$('step').onclick = () => control('step');
$('stop').onclick = async () => { try { job = await api('/api/replay/stop', {}); renderPlayer(); refresh(); } catch (error) { showError(error); } };
$('speed').onchange = () => { if (['running', 'paused'].includes(job.status)) control('speed', Number($('speed').value)); };
$('load').onclick = async () => {
  loadingReplay = true; renderPlayer();
  try {
    const start = $('replay-start').value;
    if (!start) throw Error(t('Select a UTC start minute'));
    if (active(job)) {
      job = await api('/api/replay/stop', {});
      const deadline = performance.now() + 30000;
      while (active(job)) {
        if (performance.now() > deadline) throw Error(t('Replay is still stopping'));
        await new Promise(resolve => setTimeout(resolve, 100)); job = await api('/api/replay');
      }
    }
    job = await api('/api/replay/start', {symbol: $('symbol').value, start: start + ':00Z', minutes: Number($('duration').value), speed: Number($('speed').value), paused: true});
    $('error').hidden = true; setMode('replay'); $('chart').focus({preventScroll: true});
  } catch (error) { showError(error); }
  finally { loadingReplay = false; renderPlayer(); }
};
$('history-mode').onclick = () => setMode('history'); $('live-mode').onclick = () => setMode('live');
$('replay-mode').onclick = () => {
  if ($('symbol').value !== job.symbol) { $('symbol').value = job.symbol; delete $('raw-sql').dataset.comparison; catalog(); }
  setMode('replay');
};
$('candles').onclick = () => { chartType = 'candles'; $('candles').classList.add('selected'); $('bubbles').classList.remove('selected'); drawChart(); };
$('bubbles').onclick = () => { chartType = 'bubbles'; $('bubbles').classList.add('selected'); $('candles').classList.remove('selected'); drawChart(); };
$('resolution').onchange = refresh;
$('zoom-in').onclick = () => { zoom = Math.min(16, zoom * 2); drawChart(); };
$('zoom-out').onclick = () => { zoom = Math.max(1, zoom / 2); drawChart(); };
$('fit').onclick = () => { zoom = 1; drawChart(); };
for (const id of ['flow', 'trades', 'query']) $(id + '-tab').onclick = () => panel(id);
$('sql-toggle').onclick = () => panel('query');
$('symbol').onchange = () => { inspecting++; $('minute-trades').textContent = ''; $('selection-label').textContent = ''; delete $('raw-sql').dataset.comparison; setMode(mode === 'replay' ? 'history' : mode); catalog(); };
$('benchmark').onclick = async () => {
  const symbol = $('symbol').value;
  $('benchmark').disabled = true; $('benchmark-result').textContent = t('Running three alternating trials…');
  try {
    const result = await api('/api/benchmark?symbol=' + symbol);
    if (symbol !== $('symbol').value) return;
    $('benchmark-result').textContent = `${fmt(result.trades, 0)} → ${fmt(result.buckets, 0)} · ${t(result.equal ? 'EXACT RESULTS MATCH' : 'RESULT MISMATCH')}\n${t('Raw')} ${fmt(result.raw_ms, 1)} ms / Flow ${fmt(result.flow_ms, 1)} ms · ${t('3-trial median · HTTP · local cache')}`;
    $('raw-sql').dataset.comparison = 'true'; $('raw-sql').textContent = result.raw_sql; $('flow-sql').textContent = result.flow_sql;
    $('raw-label').textContent = t('Full archive day · raw SQL');
  } catch (error) { $('benchmark-result').textContent = t(error.message); }
  finally { $('benchmark').disabled = false; }
};
document.addEventListener('keydown', event => {
  if (['INPUT', 'SELECT', 'TEXTAREA', 'BUTTON'].includes(document.activeElement?.tagName) || event.ctrlKey || event.metaKey || event.altKey) return;
  if (mode !== 'replay') return;
  if (event.code === 'Space' && !$('play').disabled) { event.preventDefault(); $('play').onclick(); }
  if (event.code === 'ArrowRight' && !$('step').disabled) { event.preventDefault(); $('step').onclick(); }
});
async function poll() {
  const requestedGeneration = generation;
  try {
    const result = await api('/api/replay');
    if (requestedGeneration === generation && !loadingReplay) {
      job = result; renderPlayer();
      if (mode === 'replay' && (data?.replay?.written !== job.written || data?.replay?.status !== job.status)) refresh();
    }
  }
  catch (error) { if (mode === 'replay') showError(error); }
  setTimeout(poll, 500);
}
if (location.hash === '#lab') panel('query');
// A replay URL outlives the in-memory session; fall back to the archive when the desk has none.
api('/api/replay').then(result => { job = result; }, () => {}).finally(() => {
  if (mode === 'replay') {
    if (job.symbol) $('symbol').value = job.symbol;
    else mode = 'history';
  }
  setMode(mode); catalog(); poll();
});
