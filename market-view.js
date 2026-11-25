'use strict';
function parseMarketEpisode(c){
 if(!c||typeof c.body!=="string"||!Number.isSafeInteger(c.id))return null;
 const b=c.body.trim();
 if(!/^MARKET_REGIME_EPISODE_V1(?:\s|$)/.test(b))return null;
 const field=(names)=>{for(const n of names){const m=b.match(new RegExp("(?:^|[;\\n])\\s*(?:-\\s*)?"+n+"\\s*[:=]\\s*([^;\\n]+)","m"));if(m)return m[1].trim();}return "";};
 const lineField=(names)=>{for(const n of names){const m=b.match(new RegExp("^\\s*(?:-\\s*)?"+n+"\\s*[:=]\\s*([^\\r\\n]+)","m"));if(m)return m[1].trim();}return "";};
 const state=field(["state"]).replace(/\.$/,""),prior=field(["prior_state"]).replace(/\.$/,""),observed=field(["observed_at_utc","observed_at"]),known=field(["known_at_utc","known_at"]),bar=field(["last_closed_bar_end_utc"]),source=field(["source"]);
 const states=["RISK_OFF","STABILIZING","RECOVERY_CONFIRMED","UNKNOWN"];
 if(!states.includes(state)||!Number.isFinite(Date.parse(observed))||!Number.isFinite(Date.parse(known))||!Number.isFinite(Date.parse(bar))||Date.parse(bar)>Date.parse(observed)||Date.parse(observed)>Date.parse(known)||!(/kraken.*eur/i.test(source)))return null;
 return {id:c.id,state,prior:states.includes(prior)?prior:null,observed,known,bar,source,core:field(["core_valid"]),refs:field(["reference_pairs_valid"]),window:lineField(["current_window_returns_pct","window_2_utc"]),counter:lineField(["counterevidence","near_term_counterevidence"])};
}
function chooseEpisode(comments,now=Date.now()){
 return comments.map(parseMarketEpisode).filter(e=>e&&Date.parse(e.known)<=now).sort((a,b)=>Date.parse(b.known)-Date.parse(a.known)||b.id-a.id)[0]||null;
}
const MARKET_REPO='hoffmannherdecke/kraken-eur-scanner';
const MARKET_ISSUE='https://github.com/'+MARKET_REPO+'/issues/7';
const MARKET_API='https://api.github.com/repos/'+MARKET_REPO;
const MARKET_RAW='https://raw.githubusercontent.com/'+MARKET_REPO+'/main/research/';
const MARKET_LABELS={RISK_OFF:'Abwärtsdruck / erhöhte Vorsicht',STABILIZING:'Stabilisierung',RECOVERY_CONFIRMED:'Erholung bestätigt',UNKNOWN:'Nicht eindeutig'};
const SOURCE_NAMES={kraken_spot_assetpairs_public:'Kraken – handelbare EUR-Paare',kraken_spot_ws_public:'Kraken – laufende Kursdaten',kraken_spot_rest_public:'Kraken – Kursprüfung',kraken_futures_public:'Kraken – Derivate',binance_futures_public:'Binance – Derivate',altrady_alert_transport:'Altrady – Markthinweise',official_fed_sec_headlines:'Fed / SEC – offizielle Meldungen',federal_reserve_fomc_calendar:'Fed – Terminkalender',coingecko_global_crosscheck:'CoinGecko – Gesamtmarkt',coinmarketcap_global_crosscheck:'CoinMarketCap – Gesamtmarkt',coinmarketcap_derivatives_crosscheck:'CoinMarketCap – Derivate',coinmarketcap_macro_calendar_secondary:'CoinMarketCap – Makrotermine',coinbase_public_spot_crosscheck:'Coinbase – Vergleichsdaten',coinmetrics_community_network_data:'CoinMetrics – On-Chain',hyperliquid_public_info:'Hyperliquid – Smart Money',polymarket_public_market_data:'Polymarket – Ereignismärkte'};
const STAGES={PILOT_READ_ONLY:'Pilot / Lesetest',WATCHLIST:'Beobachtungsliste',ACCESS_CHECK_REQUIRED:'Zugriff noch zu prüfen',BUSINESS_MODEL_RECHECK:'Angebot erneut prüfen',DISCOVERY_ONLY:'Nur Quellenentdeckung',QUARANTINED:'Ausgeschlossen / Quarantäne'};
function sourceRole(s){if(s.status==='ACTIVE')return 'Als aktiv registriert';if(s.status.startsWith('ACTIVE_'))return 'Als ergänzend / für Kontext oder Forschung registriert';if(s.status.startsWith('CONNECTED_READ_VERIFIED_MANUAL'))return 'Manueller Lesezugriff belegt';if(s.status.startsWith('PRECHECK'))return 'Vorprüfung, kein aktives Handelssignal';if(s.status.startsWith('FROZEN'))return 'Abgeschlossene Quellenauswahl';return 'Katalogisiert / noch nicht vollständig eingebunden';}
function marketLink(label,url){const a=el('a',label,'blue');a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}
async function marketJSON(url){const r=await fetch(url,{credentials:'omit',referrerPolicy:'no-referrer',cache:'no-cache',signal:AbortSignal.timeout(12000)});if(!r.ok)throw Error('Quelle nicht erreichbar');return r.json();}
async function readMarketEpisode(){
 const issue=await marketJSON(MARKET_API+'/issues/7');
 if(!Number.isSafeInteger(issue.comments)||issue.comments<1)throw Error('Keine belegten Kommentare');
 const last=Math.ceil(issue.comments/20);
 let comments=await marketJSON(MARKET_API+'/issues/7/comments?per_page=20&page='+last);
 if(!Array.isArray(comments))throw Error('Ungültige Quelle');
 // The latest page can have changed since the issue count was read. Read at most one more page.
 if(last>1&&!chooseEpisode(comments)){const older=await marketJSON(MARKET_API+'/issues/7/comments?per_page=20&page='+(last-1));if(Array.isArray(older))comments=older.concat(comments);}
 return chooseEpisode(comments);
}
function episodePanel(e){
 if(!e)return panel(el('h3','Marktphase nicht belegt','warn'),el('p','In den zuletzt gelesenen Forschungsereignissen ist keine gültige Marktphase enthalten.'),marketLink('Originale Marktbeobachtung öffnen',MARKET_ISSUE));
 const age=(Date.now()-Date.parse(e.known))/3600000;
 const p=panel(el('h3','Letzter dokumentierter Phasenwechsel','blue'),el('h2',MARKET_LABELS[e.state],e.state==='RISK_OFF'?'warn':'blue'),el('p','Zuvor: '+(MARKET_LABELS[e.prior]||'Nicht eindeutig')),el('small','Beobachtet: '+time(e.observed)),el('p','Letztes abgeschlossenes Kursintervall: '+time(e.bar),'sub'),el('p',age>4?'Der Beleg ist älter als zwei Beobachtungsintervalle. Eine aktuelle Marktphase ist daraus nicht ableitbar.':'Dies ist der letzte dokumentierte Wechsel, keine Live-Bestätigung der aktuellen Phase.','warn'),el('p','Quelle: '+e.source,'sub'));
 if(e.core||e.refs)p.append(el('p','Referenzdaten: '+[e.core,e.refs].filter(Boolean).join(' · '),'sub'));
 if(e.window)p.append(detail('Kursbewegungen im Originalbeleg',e.window));
 if(e.counter)p.append(detail('Gegenargumente / Einschränkungen',e.counter));
 p.append(marketLink('Originalbeleg auf GitHub',MARKET_ISSUE+'#issuecomment-'+e.id),el('p','Forschungskontext – kein Kaufsignal, kein Handelsverbot.','sub'));
 return p;
}
function registryPanel(reg){
 if(reg?.kind!=='EXTERNAL_SOURCE_REGISTRY_V1'||!Array.isArray(reg.sources)||!reg.sources.every(s=>typeof s.id==='string'&&typeof s.status==='string'))throw Error('Ungültiger Quellenkatalog');
 const p=panel(el('h3','Registrierte Projektquellen'),el('p',reg.sources.length+' Quellen im vorhandenen Register'),el('small','Registerstatus ist kein Nachweis laufender Abfragen oder der Verwendung durch den V3-Writer.'));
 const d=el('details');d.append(el('summary','Quellen und dokumentierte Rollen'));
 for(const s of reg.sources){const row=el('div',undefined,'split');const left=el('div');left.append(el('p',SOURCE_NAMES[s.id]||s.id),el('small',sourceRole(s)));const right=el('small',s.status);row.append(left,right);d.append(row);}
 p.append(d,marketLink('Quellenregister öffnen','https://github.com/'+MARKET_REPO+'/blob/main/research/source-registry.json'));
 return p;
}
function candidatesPanel(cat){
 if(cat?.kind!=='CRYPTO_SOURCE_DISCOVERY_CATALOG_V1'||!Array.isArray(cat.candidates)||!cat.candidates.every(s=>typeof s.name==='string'&&typeof s.stage==='string'))throw Error('Ungültiger Forschungskatalog');
 const p=panel(el('h3','Quellenbewertung in der Forschung'),el('p',cat.candidates.length+' Quellenkandidaten · Katalogstand: '+String(cat.as_of_utc||'nicht angegeben')),el('small','Ein dokumentierter Lesetest ist noch kein belegter Handelsnutzen. Keine Qualitätsrangliste ohne ausreichende unabhängige Nachweise.'));
 const d=el('details');d.append(el('summary','Bewertungs- und Prüfstand'));
 for(const s of cat.candidates){const row=el('div',undefined,'split');const left=el('div');left.append(el('p',s.name),el('small',STAGES[s.stage]||s.stage),el('p',s.automated_runtime_verified===true?'Automatischer Lesetest dokumentiert':'Automatischer Lesetest nicht belegt','sub'));if(s.runtime_verified_at_utc)left.append(el('small','Beleg: '+time(s.runtime_verified_at_utc)));if(s.quality_status)left.append(el('p',s.quality_status==='NOT_EVALUABLE_LT_5_EVENTS_2_WINDOWS'?'Für Qualitätswertung noch zu wenige geprüfte Ereignisse.':s.quality_status,'sub'));row.append(left);d.append(row);}
 p.append(d,marketLink('Forschungskatalog öffnen','https://github.com/'+MARKET_REPO+'/blob/main/research/market-source-candidates-v1.json'));
 return p;
}
let marketLoaded=false,marketBusy=false;
async function loadMarket(){
 if(marketBusy||!data)return;
 marketBusy=true;$('market-refresh').disabled=true;$('market-note').textContent='Vorhandene Forschungsbelege werden gelesen …';
 const results=await Promise.allSettled([readMarketEpisode(),marketJSON(MARKET_RAW+'source-registry.json'),marketJSON(MARKET_RAW+'market-source-candidates-v1.json')]);
 const renderers=[episodePanel,registryPanel,candidatesPanel],ids=['market-phase','market-registry','market-candidates'];
 let good=0;
 for(let i=0;i<ids.length;i++){try{if(results[i].status!=='fulfilled')throw Error('Nicht verfügbar');put(ids[i],renderers[i](results[i].value));good++;}catch{put(ids[i],panel(el('h3','Datenquelle derzeit nicht verfügbar','warn'),el('p','Kein aktueller Abruf bestätigt. Keine Ersatzwerte.')));}}
 $('market-note').textContent=good===3?'Forschungsquellen abgerufen: '+time(new Date().toISOString()):'Abruf teilweise oder vollständig fehlgeschlagen. Bitte bei Bedarf erneut abrufen.';
 marketLoaded=good===3;marketBusy=false;$('market-refresh').disabled=false;
}
document.querySelector('nav button[data-page="market"]').addEventListener('click',()=>{if(!marketLoaded)loadMarket();});
$('market-refresh').addEventListener('click',loadMarket);
