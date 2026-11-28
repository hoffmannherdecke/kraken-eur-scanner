'use strict';
function observeAppEvents(previous,snapshot,current=true){
 const empty={series:null,readAt:null,items:[]};
 if(!current)return previous||empty;
 const series=Array.isArray(snapshot?.series)&&snapshot.series.length===1&&snapshot.series[0]?.status==="active"?snapshot.series[0].series_id:null;
 const now=Date.parse(snapshot?.read_at);
 if(typeof series!=="string"||!series||!Number.isFinite(now)||!Array.isArray(snapshot?.decisions))return empty;
 if(!previous||previous.series!==series||!Number.isFinite(previous.readAt)||now<previous.readAt)return {series,readAt:now,items:[]};
 const items=new Map(previous.items.map(e=>[e.id,e]));
 const h=paperTradeHistory(snapshot);for(const d of [...snapshot.decisions.filter(d=>d.phase!=='PAPER_FILL'&&d.phase!=='PAPER_EXIT'),...(h?h.rows:[])]){
 const received=Date.parse(d?.received_at),known=Date.parse(d?.source_known_at);
 if(typeof d?.candidate_id!=="string"||!d.candidate_id||typeof d.pair!=="string"||!/^[A-Z0-9]{1,20}\/EUR$/.test(d.pair)||!Number.isFinite(received)||!Number.isFinite(known)||known>received||received<=previous.readAt||received>now)continue;
 const label=d.phase==="P4_VALIDATION"&&d.result==="BUY_SCOUT"?"Einstiegsentscheidung – Füllung nicht belegt":d.phase==="PAPER_FILL"&&d.result==="PAPER_FILLED"?"Virtueller Paper-Einstieg belegt":d.phase==="PAPER_EXIT"&&d.result==="CLOSED"?"Paper-Abschluss belegt":null;
 if(!label)continue;
 const id=JSON.stringify([d.candidate_id,d.phase,d.result,received]);
 items.set(id,{id,pair:d.pair,label,known:d.source_known_at,received:d.received_at});
 }
 return {series,readAt:now,items:[...items.values()].sort((a,b)=>Date.parse(b.received)-Date.parse(a.received)||a.id.localeCompare(b.id)).slice(0,20)};
}
let appEventState=null;
function resetAppEvents(){appEventState=null;put('app-events');}
function renderAppEvents(v,current=true){
 appEventState=observeAppEvents(appEventState,v,current);
 const p=panel(el('h3','Wichtige neue Belege'),el('small','Seit Anmeldung in dieser App beobachtet. Keine vollständige Historie, keine Push-Zustellbestätigung.'));
 if(!current)p.append(el('p','Keine aktuelle Cloud-Verbindung – letzter beobachteter Stand.','warn'));
 if(!appEventState.items.length)p.append(el('p','Noch keine neuen Einstiegsentscheidungen, Einstiegs- oder Abschlussbelege in dieser Sitzung beobachtet.','muted'));
 for(const e of appEventState.items){const row=el('div',undefined,'split'),d=el('div');d.append(el('h3',e.pair),el('p',e.label),el('small','Belegt: '+time(e.known)+' · Cloud-Eingang: '+time(e.received)));row.append(d);p.append(row);}
 p.append(el('p','Dringende Betriebs- und Handlungsmeldungen bleiben beim bestehenden Slack-/iPhone-Meldeweg.','sub'));put('app-events',p);
}