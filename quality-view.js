'use strict';
function decisionQuality(v,current=true){
 const n=x=>Number.isSafeInteger(x)&&x>=0;
 if(v?.window_hours!==24||v.series?.length!==1||v.series[0]?.status!=="active"||!Number.isFinite(Date.parse(v.read_at))||![v.events_count,v.candidate_count,v.fill_count,v.exit_count].every(n)||v.candidate_count>v.events_count||!Array.isArray(v.decisions)||v.decisions.length>30||v.decisions.length>v.candidate_count)return null;
 const groups={WAIT:0,REJECT:0,BUY_SCOUT:0,PAPER_FILLED:0,CLOSED:0,UNKNOWN:0,OTHER:0},ids=new Set(),reasons=new Map(),phases=new Map();
 const validPhases=new Set(["P4_VALIDATION","WAIT_RECHECK","WAIT_EXPIRY","WAIT_WATCH","PAPER_FILL","PAPER_EXIT"]);
 for(const d of v.decisions){
 if(typeof d?.candidate_id!=="string"||!d.candidate_id||ids.has(d.candidate_id)||typeof d.pair!=="string"||!validPhases.has(d.phase)||typeof d.result!=="string")return null;
 const known=Date.parse(d.source_known_at),received=Date.parse(d.received_at),at=Date.parse(v.read_at);
 if(!Number.isFinite(known)||!Number.isFinite(received)||known>at||received>at||known<at-86400000)return null;
 ids.add(d.candidate_id);let k="OTHER";
 if(d.phase==="PAPER_FILL"&&d.result==="PAPER_FILLED")k="PAPER_FILLED";
 else if(d.phase==="PAPER_EXIT"&&d.result==="CLOSED")k="CLOSED";
 else if(["P4_VALIDATION","WAIT_RECHECK","WAIT_WATCH","WAIT_EXPIRY"].includes(d.phase)&&["WAIT","REJECT","BUY_SCOUT","UNKNOWN"].includes(d.result))k=d.result;
 groups[k]++;
 phases.set(d.phase,(phases.get(d.phase)||0)+1);
 for(const code of new Set((Array.isArray(d.reasons)?d.reasons:[]).filter(r=>typeof r==="string"&&r.trim()).slice(0,30)))reasons.set(code,(reasons.get(code)||0)+1);
 }
 return {current,readAt:v.read_at,candidates:v.candidate_count,events:v.events_count,listed:ids.size,notListed:v.candidate_count-ids.size,fills:v.fill_count,exits:v.exit_count,groups,phases:[...phases.entries()],reasons:[...reasons.entries()].sort((a,b)=>b[1]-a[1]||a[0].localeCompare(b[0]))};
}
const QUALITY_LABELS={WAIT:'Warten',REJECT:'Abgelehnt',BUY_SCOUT:'Einstiegsentscheidung',PAPER_FILLED:'Einstiegsbeleg',CLOSED:'Abschlussbeleg',UNKNOWN:'Unklar',OTHER:'Andere Zustände'};
const QUALITY_PHASES={P4_VALIDATION:'Entscheidungsprüfung',WAIT_RECHECK:'Warte-Nachprüfung',WAIT_EXPIRY:'Wartefristprüfung',WAIT_WATCH:'Warteüberwachung',PAPER_FILL:'Paper-Einstieg',PAPER_EXIT:'Paper-Abschluss'};
function renderDecisionQuality(v,current=true){
 const m=decisionQuality(v,current);
 if(!m){put('decision-quality',panel(el('h3','Entscheidungsstatistik nicht eindeutig','warn'),el('p','Der aktuelle Cloud-Abruf erfüllt die Anforderungen dieser Auswertung nicht.')));return;}
 const p=panel(el('h3','Entscheidungsstatistik · letzte 24 Stunden',m.current?'blue':'warn'),el('small','Stand: '+time(m.readAt)),el('p',m.listed+' von '+m.candidates+' Kandidaten mit angezeigtem letztem Entscheidungsbeleg'));
 if(!m.current)p.append(el('p','Letzter erfolgreicher Abruf – nicht aktuell.','warn'));
 const metrics=el('div',undefined,'metrics');metrics.append(metric(m.events,'Journalbelege'),metric(m.listed,'Angezeigte Kandidaten'));p.append(metrics);
 if(m.notListed)p.append(el('p',m.notListed+' Kandidaten ohne angezeigten Entscheidungsbeleg in dieser begrenzten Liste.','warn'));
 const bar=el('div',undefined,'quality-bar');bar.setAttribute('aria-label','Verteilung der angezeigten letzten Zustände');
 for(const [key,n] of Object.entries(m.groups)){if(n&&m.listed){const part=el('div',undefined,'quality-segment quality-'+key);part.style.flexGrow=String(n);part.title=QUALITY_LABELS[key]+': '+n;bar.append(part);}}
 if(m.listed)p.append(bar);
 for(const [key,n] of Object.entries(m.groups)){const r=el('div',undefined,'split');r.append(el('span',QUALITY_LABELS[key]),el('strong',String(n)));p.append(r);}
 p.append(el('small','Je Kandidat nur der letzte im Abruf enthaltene Entscheidungsbeleg, maximal 30. Keine Erstentscheidungs-, Umwandlungs- oder vollständige Verlaufstatistik.'));
 const r=panel(el('h3','Dokumentierte Entscheidungsgründe'),el('small','Zuletzt verfügbarer P4-Grund je angezeigtem Kandidaten, nicht zwingend Ursache des letzten Zustands. Mehrfachnennung möglich.'));
 for(const [code,n] of m.reasons){const line=el('div',undefined,'split');line.append(el('span',reasonMap[code]||code),el('strong',String(n)));r.append(line);}
 if(!m.reasons.length)r.append(el('p','Keine Gründe im gelieferten Ausschnitt.','muted'));
 const phase=el('details');phase.append(el('summary','Letzte Prüfphasen'));for(const [k,n] of m.phases)phase.append(el('p',(QUALITY_PHASES[k]||k)+': '+n));r.append(phase);
 const trade=panel(el('h3','Handelsqualität · Nachweisgrenzen'),el('p',paperTradeLabel(v)),el('p','Trefferquote, Gebühren-/Spread-/Slippage-Ergebnis, Drawdown und verpasste Chancen sind aus der vorhandenen 24-Stunden-Schnittstelle nicht belastbar bestimmbar.','warn'),el('small','Keine Bewertung der Handelsqualität allein aus Ablehnungsquote oder fehlenden Einstiegen.'));
 put('decision-quality',p,r,trade);
}