'use strict';
function newsURL(raw,host){if(typeof raw!=="string"||!["www.federalreserve.gov","www.sec.gov"].includes(host)||/[\s\\\u0000-\u001f\u007f]/.test(raw)||!raw.startsWith("https://"+host+"/"))return null;return raw;}
function newsItems(rows,kind,now){
 if(!Array.isArray(rows)||!["fed","sec"].includes(kind)||!Number.isFinite(now))throw Error("Ungültige Quelle");
 const host=kind==="fed"?"www.federalreserve.gov":"www.sec.gov",out=new Map();
 for(const r of rows.slice(0,100)){
 const title=typeof r?.title==="string"?r.title.trim().replace(/\s+/g," "):"",link=newsURL(r?.link,host),at=Date.parse(r?.date);
 if(!title||title.length>500||!link||!Number.isFinite(at)||at>now||now-at>7*86400000)continue;
 if(kind==="sec"&&!/\b(?:crypto(?:currency|currencies|assets?)?|digital[\s-]assets?|bitcoin|ethereum|ether|stablecoins?|blockchain|tokeniz(?:ation|ed)|tokenis(?:ation|ed))\b/i.test(title))continue;
 const coins=[];if(/\b(?:bitcoin|BTC)\b/i.test(title))coins.push("BTC");if(/\b(?:ethereum|ether|ETH)\b/i.test(title))coins.push("ETH");if(/\b(?:solana|SOL)\b/i.test(title))coins.push("SOL");
 out.set(link,{title,link,date:new Date(at).toISOString(),coins,topic:kind==="fed"?"Geldpolitik / Gesamtmarkt":"Kryptoregulierung",relevance:kind==="fed"?"Makro-Kontext – Risikoanlagen":"Direkter Krypto-Themenbezug der Überschrift",impact:kind==="fed"?"Zins- und Liquiditätserwartungen können sich ändern. Positive oder negative Kurswirkung aus der Überschrift nicht bestimmbar.":"Regeln oder Marktbedingungen können betroffen sein. Kursrichtung und tatsächliche Betroffenheit einzelner Coins sind nicht belegt."});
 }return [...out.values()].sort((a,b)=>Date.parse(b.date)-Date.parse(a.date)).slice(0,8);
}
function calendarItems(v,now){
 if(v?.kind!=="V3_H5_OFFICIAL_EVENT_CALENDAR_CAPTURE_V1"||v.status!=="PROSPECTIVE_CAPTURE"||!Array.isArray(v.events)||!Array.isArray(v.sources)||!Number.isFinite(Date.parse(v.captured_at_utc))||Date.parse(v.captured_at_utc)>now)throw Error("Kalender nicht belegt");
 const sources=new Map(v.sources.map(s=>[s.id,newsURL(s.url,"www.federalreserve.gov")]));
 return v.events.filter(e=>["FOMC_POLICY_STATEMENT","FOMC_PRESS_CONFERENCE"].includes(e?.event_family)&&Number.isFinite(Date.parse(e.scheduled_utc))&&Date.parse(e.scheduled_utc)>=now&&Number.isFinite(Date.parse(e.known_at_utc))&&Date.parse(e.known_at_utc)<=now&&Date.parse(e.known_at_utc)>=Date.parse(v.captured_at_utc)&&Array.isArray(e.source_ids)&&e.source_ids.length>0&&e.source_ids.every(s=>sources.get(s))).sort((a,b)=>Date.parse(a.scheduled_utc)-Date.parse(b.scheduled_utc)).slice(0,6).map(e=>({label:e.event_family==="FOMC_POLICY_STATEMENT"?"Fed-Zinsentscheidung / Erklärung":"Fed-Pressekonferenz",at:e.scheduled_utc,known:e.known_at_utc,link:sources.get(e.source_ids[0])}));
}
const NEWS_FEEDS=[{id:'fed',label:'Federal Reserve – Geldpolitik',url:'https://www.federalreserve.gov/feeds/press_monetary.xml',home:'https://www.federalreserve.gov/newsevents/pressreleases.htm'},{id:'sec',label:'SEC – Krypto-Regulierung',url:'https://www.sec.gov/news/pressreleases.rss',home:'https://www.sec.gov/newsroom/press-releases'}];
let newsGeneration=0,newsBusy=false,newsAttempt=0,newsCalendarDone=false;
function resetNews(){newsGeneration++;newsBusy=false;newsAttempt=0;newsCalendarDone=false;put('news-feeds');put('news-calendar');put('news-pilots');$('news-note').textContent='Abruf bei sichtbarer Marktansicht.';$('news-refresh').disabled=false;}
async function readOfficialNews(feed){
 const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),12000);
 try{
 const r=await fetch(feed.url,{method:'GET',credentials:'omit',referrerPolicy:'no-referrer',cache:'no-store',signal:ctrl.signal});if(!r.ok)throw Error('Feed nicht erreichbar');
 const xml=await r.text();if(xml.length>1000000||/<!DOCTYPE|<!ENTITY/i.test(xml))throw Error('Ungültiger RSS-Inhalt');
 const d=new DOMParser().parseFromString(xml,'application/xml');if(d.querySelector('parsererror')||d.documentElement.localName!=='rss'||!d.querySelector('channel'))throw Error('Ungültiges RSS-Format');
 const items=[...d.querySelectorAll('channel > item')].slice(0,100).map(i=>({title:i.querySelector('title')?.textContent,link:i.querySelector('link')?.textContent,date:i.querySelector('pubDate')?.textContent}));
 if(!items.length)throw Error('Keine lesbaren Feed-Elemente');
 return newsItems(items,feed.id,Date.now());
 }finally{clearTimeout(timer);}
}
function newsFeedPanel(feed,result){
 const p=panel(el('h3',feed.label));
 if(result.status!=='fulfilled'){p.append(el('p','Automatischer Feed-Abruf nicht bestätigt (Browser, Netzwerk oder Quelle).','warn'),marketLink('Amtliche Meldungen direkt öffnen',feed.home));return p;}
 p.append(el('small','Feed gelesen: '+time(new Date().toISOString())+' · Auswahl der letzten 7 Tage, keine vollständige Nachrichtenabdeckung.'));
 if(!result.value.length)p.append(el('p','Keine passenden datierten Meldungen in diesem Feed-Ausschnitt. Das beweist nicht, dass keine Ereignisse vorliegen.','muted'));
 for(const n of result.value){const item=panel(el('h3',n.topic,'blue'),marketLink(n.title,n.link),el('p','Veröffentlicht: '+time(n.date),'sub'),el('p','Relevanz: '+n.relevance),el('p',n.coins.length?'Im Titel ausdrücklich genannt: '+n.coins.join(', '):'Kein einzelner Coin im Titel eindeutig zugeordnet.','sub'),el('p',n.impact,'sub'));p.append(item);}
 return p;
}
function newsCalendarPanel(v){
 const upcoming=calendarItems(v,Date.now());
 const p=panel(el('h3','Vorgemerkte Makrotermine'),el('p','Vorhandener amtlicher Kalenderbeleg aus dem Projekt, erfasst: '+time(v.captured_at_utc)),el('small','Historischer Erfassungsstand – Terminänderungen vor Nutzung an der offiziellen Quelle prüfen. Kein neuer Kalender-Abruf.'));
 if(!upcoming.length)p.append(el('p','Keine zukünftigen Termine in diesem Beleg.','warn'));
 for(const e of upcoming)p.append(el('p',e.label+' · '+time(e.at)),marketLink('Offiziellen Kalender prüfen',e.link));
 p.append(el('p','Mögliche Wirkung: höhere Schwankungen rund um geldpolitische Entscheidungen. Keine Prognose der Kursrichtung, kein Kaufsignal.','sub'));return p;
}
function renderNewsPilots(cat){
 const p=panel(el('h3','Redaktionelle Quellen im Projekt'),el('small','Bestehende Forschungsbewertungen, keine Live-Feeds.'));
 const candidates=Array.isArray(cat?.candidates)?cat.candidates.filter(s=>s.category==='news'&&['PILOT_READ_ONLY','WATCHLIST'].includes(s.stage)):[];
 for(const s of candidates){
 let u;try{u=new URL(s.url);if(u.protocol!=='https:'||u.username||u.password)continue;}catch{continue;}
 const item=el('div',undefined,'split'),left=el('div');left.append(marketLink(s.name,u.href),el('p',s.stage==='PILOT_READ_ONLY'?'Lesepilot':'Beobachtungsliste','sub'),el('small',s.automated_runtime_verified===true?'Historischer automatischer Lesetest belegt':'Automatischer Lesetest nicht belegt'));
 if(s.quality_status==='NOT_EVALUABLE_LT_5_EVENTS_2_WINDOWS')left.append(el('p','Für belastbare Qualitätswertung noch zu wenig geprüfte Ereignisse.','sub'));
 if(s.runtime_verified_at_utc)left.append(el('small','Teststand: '+time(s.runtime_verified_at_utc)));
 if(s.needs_primary_confirmation)left.append(el('p','Primärbestätigung erforderlich.','sub'));
 item.append(left);p.append(item);
 }
 p.append(el('p','Keine neue Quellenbewertung und kein Nachweis, dass eine Nachricht die aktive Strategie beeinflusst hat.','sub'));put('news-pilots',p);
}
async function refreshNews(force=false){
 if(!data||document.hidden||$('market').hidden||newsBusy)return;
 const now=Date.now();if(!force&&newsAttempt&&now-newsAttempt<3600000)return;
 const g=newsGeneration;newsBusy=true;newsAttempt=now;$('news-refresh').disabled=true;$('news-note').textContent='Amtliche öffentliche Feeds werden gelesen …';
 try{
 const jobs=NEWS_FEEDS.map(readOfficialNews);const withCalendar=!newsCalendarDone||force;
 if(withCalendar)jobs.push(marketJSON(MARKET_RAW+'v3/event-calendars/fomc-prospective-capture-20261001.json'));
 const r=await Promise.allSettled(jobs);if(g!==newsGeneration)return;
 put('news-feeds',...NEWS_FEEDS.map((f,i)=>newsFeedPanel(f,r[i])));
 if(withCalendar){try{if(r[2].status!=='fulfilled')throw Error();put('news-calendar',newsCalendarPanel(r[2].value));newsCalendarDone=true;}catch{put('news-calendar',panel(el('p','Dokumentierter Kalenderbeleg nicht verfügbar.','warn')));}}
 const good=r.slice(0,2).filter(x=>x.status==='fulfilled').length;
 $('news-note').textContent='Abrufversuch: '+time(new Date().toISOString())+' · '+good+'/2 amtliche Feeds erfolgreich. Automatisch höchstens stündlich bei sichtbarer Marktansicht.';
 }finally{if(g===newsGeneration){newsBusy=false;$('news-refresh').disabled=false;}}
}
function markNewsPaused(){newsGeneration++;newsBusy=false;newsAttempt=0;$('news-refresh').disabled=false;$('news-note').textContent='Cloud-Verbindung unterbrochen – automatische Nachrichtenaktualisierung pausiert. Frühere Anzeigen sind nicht neu bestätigt.';}
document.querySelector('nav button[data-page="market"]').addEventListener('click',()=>refreshNews());
$('news-refresh').addEventListener('click',()=>refreshNews(true));
