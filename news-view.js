'use strict';
function newsURL(raw,host){if(typeof raw!=="string"||!["www.federalreserve.gov","www.sec.gov"].includes(host)||/[\s\\\u0000-\u001f\u007f]/.test(raw)||!raw.startsWith("https://"+host+"/"))return null;return raw;}
function parseProjectNews(comments,now){
 const map=new Map();const day=new Date(now).toISOString().slice(0,10),cut=new Date(now-7*86400000).toISOString().slice(0,10);
 for(const c of comments){
 if(!Number.isSafeInteger(c?.id)||typeof c.body!=="string"||!c.body.startsWith("MARKET_NEWS_EVIDENCE_V1\n"))continue;
 const observed=Date.parse(c.created_at);if(!Number.isFinite(observed)||observed>now)continue;
 let r;try{r=JSON.parse(c.body.slice("MARKET_NEWS_EVIDENCE_V1\n".length));}catch{continue;}
 if(!r||!["fed","sec","cftc","bls"].includes(r.source)||!["MANUAL_VERIFIED","EXISTING_RADAR_VERIFIED"].includes(r.origin)||!["MACRO","REGULATION","SECURITY"].includes(r.topic)||typeof r.title!=="string"||!r.title.trim()||r.title.length>240||typeof r.fact!=="string"||!r.fact.trim()||r.fact.length>500||typeof r.published_date!=="string"||!/^\d{4}-\d{2}-\d{2}$/.test(r.published_date)||!Number.isFinite(Date.parse(r.published_date))||new Date(r.published_date).toISOString().slice(0,10)!==r.published_date||r.published_date>day||r.published_date<cut||r.published_date>new Date(observed).toISOString().slice(0,10))continue;
 const host={fed:"www.federalreserve.gov",sec:"www.sec.gov",cftc:"www.cftc.gov",bls:"www.bls.gov"}[r.source];
 if(typeof r.url!=="string"||!r.url.startsWith("https://"+host+"/")||/[\s\\\u0000-\u001f\u007f]/.test(r.url))continue;
 if(!Array.isArray(r.coins)||r.coins.length>8||!r.coins.every(x=>typeof x==="string"&&/^[A-Z0-9]{2,15}$/.test(x))||r.direction!=="UNKNOWN"||r.authority!=="RESEARCH_ONLY")continue;
 const prior=map.get(r.url);if(!prior||observed>Date.parse(prior.known))map.set(r.url,{...r,id:c.id,known:c.created_at});
 }
 return [...map.values()].sort((a,b)=>b.published_date.localeCompare(a.published_date)||Date.parse(b.known)-Date.parse(a.known)).slice(0,12);
}
function calendarItems(v,now){
 if(v?.kind!=="V3_H5_OFFICIAL_EVENT_CALENDAR_CAPTURE_V1"||v.status!=="PROSPECTIVE_CAPTURE"||!Array.isArray(v.events)||!Array.isArray(v.sources)||!Number.isFinite(Date.parse(v.captured_at_utc))||Date.parse(v.captured_at_utc)>now)throw Error("Kalender nicht belegt");
 const sources=new Map(v.sources.map(s=>[s.id,newsURL(s.url,"www.federalreserve.gov")]));
 return v.events.filter(e=>["FOMC_POLICY_STATEMENT","FOMC_PRESS_CONFERENCE"].includes(e?.event_family)&&Number.isFinite(Date.parse(e.scheduled_utc))&&Date.parse(e.scheduled_utc)>=now&&Number.isFinite(Date.parse(e.known_at_utc))&&Date.parse(e.known_at_utc)<=now&&Date.parse(e.known_at_utc)>=Date.parse(v.captured_at_utc)&&Array.isArray(e.source_ids)&&e.source_ids.length>0&&e.source_ids.every(s=>sources.get(s))).sort((a,b)=>Date.parse(a.scheduled_utc)-Date.parse(b.scheduled_utc)).slice(0,6).map(e=>({label:e.event_family==="FOMC_POLICY_STATEMENT"?"Fed-Zinsentscheidung / Erklärung":"Fed-Pressekonferenz",at:e.scheduled_utc,known:e.known_at_utc,link:sources.get(e.source_ids[0])}));
}

let newsGeneration=0,newsBusy=false,newsCalendarDone=false;
function resetNews(){newsGeneration++;newsBusy=false;newsCalendarDone=false;put('news-feeds');put('news-calendar');put('news-pilots');$('news-note').textContent='Abruf vorhandener Projektbelege bei sichtbarer Marktansicht.';$('news-refresh').disabled=false;}
function renderProjectNews(comments){
 const items=parseProjectNews(comments,Date.now());
 const p=panel(el('h3','Geprüfte Nachrichtenbelege aus dem Quellenmanagement'),el('small','Letzte 7 Kalendertage im begrenzten Ausschnitt von Issue #7. Kein vollständiger Live-Feed.'));
 if(!items.length)p.append(el('p','Keine passenden geprüften Nachrichten im gelesenen Ausschnitt. Das bedeutet nicht, dass es keine Marktnachrichten gibt.','warn'));
 const labels={fed:'Federal Reserve',sec:'SEC',cftc:'CFTC',bls:'BLS'};
 const relevance={MACRO:'Gesamtmarkt / Zins- und Liquiditätskontext',REGULATION:'Regulatorischer Kontext',SECURITY:'Sicherheits- und Anlegerschutzkontext'};
 for(const e of items){const q=panel(el('h3',e.title,'blue'),el('p',e.fact),el('p',labels[e.source]+' · veröffentlicht: '+e.published_date.split('-').reverse().join('.'),'sub'),el('p','Relevanz: '+relevance[e.topic]),el('p',e.coins.length?'Explizit belegte Coin-Bezüge: '+e.coins.join(', '):'Kein einzelner Coin eindeutig zugeordnet.','sub'),el('p','Kurswirkung nicht belegt. Kein Handelssignal.','warn'),el('small',(e.origin==='MANUAL_VERIFIED'?'Manuell verifiziert':'Vom bestehenden Radar verifiziert')+' · Projektbeleg: '+time(e.known)),marketLink('Amtliche Originalmeldung',e.url),el('p'),marketLink('Projektbeleg',MARKET_ISSUE+'#issuecomment-'+e.id));p.append(q);}
 p.append(el('p','Offizielle Quellen direkt:','sub'),marketLink('Fed-Meldungen','https://www.federalreserve.gov/newsevents/pressreleases.htm'),el('p'),marketLink('SEC-Meldungen','https://www.sec.gov/newsroom/press-releases'));put('news-feeds',p);
 $('news-note').textContent='Projektbelege gelesen: '+time(new Date().toISOString())+' · '+items.length+' Meldungen. Aktualisierung mit bestehendem 15-Minuten-Marktbelegabruf. Neue Fakten nur aus vorhandenem Quellenprozess.';
}
function markProjectNewsUnavailable(){put('news-feeds',panel(el('p','Nachrichtenbelege derzeit nicht lesbar. Keine Ersatzmeldungen.','warn')));$('news-note').textContent='Projektabruf nicht bestätigt.';}
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
 if(!data||document.hidden||$('market').hidden||newsBusy||newsCalendarDone&&!force)return;
 const g=newsGeneration;newsBusy=true;
 try{const v=await marketJSON(MARKET_RAW+'v3/event-calendars/fomc-prospective-capture-20261001.json');if(g!==newsGeneration)return;put('news-calendar',newsCalendarPanel(v));newsCalendarDone=true;}catch{if(g===newsGeneration)put('news-calendar',panel(el('p','Dokumentierter Kalenderbeleg nicht verfügbar.','warn')));}finally{if(g===newsGeneration)newsBusy=false;}
}
function markNewsPaused(){newsGeneration++;newsBusy=false;$('news-note').textContent='Cloud-Verbindung unterbrochen – automatische Aktualisierung pausiert. Frühere Anzeigen nicht neu bestätigt.';}
document.querySelector('nav button[data-page="market"]').addEventListener('click',()=>refreshNews());
$('news-refresh').addEventListener('click',()=>{loadMarket(true);refreshNews(true);});
