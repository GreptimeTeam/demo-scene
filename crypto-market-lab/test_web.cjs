const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const language = process.argv[2] || 'en';
const zh = language === 'zh-CN';
const html = fs.readFileSync(`${__dirname}/web/index.html`, 'utf8');
function element() {
  const classes = new Set();
  return {value:'', hidden:false, disabled:false, textContent:'', innerHTML:'', dataset:{}, style:{}, attrs:{}, events:{},
    classList:{add(name){classes.add(name);},remove(name){classes.delete(name);},toggle(name,on){on?classes.add(name):classes.delete(name);}},
    addEventListener(name,fn){this.events[name]=fn;},setAttribute(key,val){this.attrs[key]=val;},
    getAttribute(key){return this.attrs[key];},hasAttribute(key){return key in this.attrs;},
    getBoundingClientRect(){return {left:0,top:0,width:900,height:400};}};
}
const elements = new Map([...html.matchAll(/id="([^"]+)"/g)].map(match=>[match[1],element()]));
elements.get('symbol').value='BTCUSDT';elements.get('resolution').value='1 minute';
elements.get('speed').value='10';elements.get('duration').value='5';
const staticElements=[...html.matchAll(/<[^>]*data-i18n="([^"]+)"[^>]*>/g)].map(match=>{
  const id=match[0].match(/id="([^"]+)"/);const el=id?elements.get(id[1]):element();
  el.dataset.i18n=match[1].replaceAll('&amp;','&');return el;
});
const start=1794528000000000;
const frame={symbol:'BTCUSDT',mode:'history',dataset:'market',start,end:start+60e6,now:start+60e6,resolution:'1 minute',
  summary:[2,'3','302','1',start+1000,'100','101'],latest:[['101',start+1000]],
  candles:[[start,'100','101','100','101','3','1',2,'302']],
  tape:[[start+1000,'101','2','202',false,12],[start,'100','1','100',true,11]],
  quotes:[],profile:[[100,1,2]],profile_step:2,candle_sql:'SELECT chart'};
const calls=[];const storage=new Map();const events={};
const location={hash:'',search:'?lang='+language,href:'http://localhost:25200/?lang='+language,assign(url){this.assigned=url;}};
const context=vm.createContext({
  document:{documentElement:{},activeElement:null,getElementById(id){return elements.get(id)||null;},
    querySelectorAll(selector){return selector==='[data-i18n]'?staticElements:[];},addEventListener(name,fn){events[name]=fn;}},
  window:{history:{replaceState(a,b,url){location.href=url;}}},location,URL,URLSearchParams,navigator:{language:'en-US'},
  localStorage:{getItem(key){return storage.get(key);},setItem(key,value){storage.set(key,value);}},
  setTimeout(){return 1;},clearTimeout(){},performance:{now:()=>1},Intl,Date,Math,Number,Error,Set,
  fetch:async(path,options)=>{calls.push([path,options]);return {ok:true,json:async()=>{
    if(path.startsWith('/api/desk')) return frame;
    if(path.startsWith('/api/catalog')) return [[start,start+86400e6-1]];
    if(path==='/api/replay') return {status:'idle'};
    if(path.startsWith('/api/benchmark')) return {trades:2,buckets:1,equal:true,raw_ms:8,flow_ms:2,raw_sql:'SELECT raw',flow_sql:'SELECT flow'};
    if(path.startsWith('/api/minute')) return {rows:[[start,11,'100','1','100',true]],sql:'SELECT minute'};
    if(path==='/api/replay/control') return {status:'paused',symbol:'BTCUSDT',written:1,total:2,speed:10};
    throw Error(path);
  }};}
});
for(const file of ['i18n.js','app.js']) vm.runInContext(fs.readFileSync(`${__dirname}/web/${file}`,'utf8'),context);
(async()=>{
  await new Promise(resolve=>setImmediate(resolve));
  assert.match(elements.get('chart').innerHTML,/<svg/);
  assert(!elements.get('chart').innerHTML.includes('NaN'));
  assert.match(elements.get('tape').innerHTML,/101\.00/);
  assert.equal(elements.get('last-price').textContent,'101.00');
  elements.get('bubbles').onclick();
  assert.match(elements.get('chart').innerHTML,/<circle/);
  assert.match(elements.get('chart-info').textContent,zh?/气泡/:/size = volume/);
  await vm.runInContext(`inspect(${start+1000})`,context);
  assert.equal(elements.get('trades-panel').hidden,false);
  assert.match(elements.get('minute-trades').innerHTML,zh?/主动买入/:/BUY/);
  elements.get('sql-toggle').onclick();
  assert.equal(elements.get('query-panel').hidden,false);
  await elements.get('benchmark').onclick();
  assert.match(elements.get('benchmark-result').textContent,zh?/结果完全一致/:/EXACT RESULTS MATCH/);
  assert.equal(elements.get('flow-sql').textContent,'SELECT flow');
  vm.runInContext("job={status:'paused',symbol:'BTCUSDT',written:1,total:2,speed:10}; renderPlayer()",context);
  assert.equal(elements.get('step').disabled,false);
  assert.equal(elements.get('play').disabled,false);
  await elements.get('step').onclick();
  assert(calls.some(([path,opts])=>path==='/api/replay/control'&&JSON.parse(opts.body).action==='step'));
  vm.runInContext("setMode('replay')", context);
  assert.equal(elements.get('last-price').textContent,'—');
  assert.equal(elements.get('tape').textContent,'');
  assert.equal(elements.get('minute-trades').textContent,'');
  elements.get('language').onchange({target:{value:zh?'en':'zh-CN'}});
  const switched=new URL(location.assigned);
  assert.equal(switched.searchParams.get('mode'),'replay');
  assert.equal(switched.searchParams.get('symbol'),'BTCUSDT');
  assert.equal(storage.get('crypto-desk-language'),zh?'en':'zh-CN');
  if(zh) for(const el of staticElements) assert.notEqual(el.textContent,el.dataset.i18n,el.dataset.i18n);
  console.log(language+' PASS chart / bubbles / tape / inspection / SQL / playback controls / language');
})().catch(error=>{console.error(error);process.exitCode=1;});
