'use strict';
function healthModel(v,elapsedSec,connected){
 const unknown=(label,note)=>({tone:"unknown",label,note,hostAge:null,hostAt:null,writer:"Unbekannt",scanner:"Unbekannt"});
 if(!v||!Array.isArray(v.hosts)||!Number.isFinite(elapsedSec)||elapsedSec<0)return unknown("Systemstatus nicht bekannt","Noch kein bestätigter Betriebsbericht.");
 const hosts=v.hosts.filter(h=>h?.node_id==="MINI-PC");
 if(hosts.length!==1)return unknown("Mini-PC nicht eindeutig belegt","Kein eindeutiger Originalhost-Bericht.");
 const h=hosts[0],read=Date.parse(v.read_at),observed=Date.parse(h.observed_at),baseAge=(read-observed)/1000;
 if(!Number.isFinite(baseAge)||baseAge< -30)return unknown("Systembericht zeitlich unklar","Zeitstempel fehlen oder sind widersprüchlich.");
 const age=Math.max(0,baseAge+elapsedSec),issues=Array.isArray(h.issues)?h.issues:[],writerIssue=issues.find(i=>i?.check==="v3_paper_single_writer");
 const writer=h.writer?.ok===false||writerIssue?false:h.writer?.ok===true?true:null,scanner=h.scanner_ok===true?true:h.scanner_ok===false?false:null;
 const critical=h.status==="CRITICAL"||issues.some(i=>i?.severity==="CRITICAL"),negative=critical||writer===false||scanner===false;
 const stale=!connected||elapsedSec>CLOUD_RESPONSE_STALE_SEC||age>HOST_REPORT_STALE_SEC;
 const active=Array.isArray(v.series)&&v.series.length===1&&v.series[0]?.status==="active";
 const result={hostAge:Math.floor(age),hostAt:h.observed_at,writer:writer===true?"Beim Bericht OK":writer===false?"Prüfung fehlgeschlagen":"Nicht belegt",scanner:scanner===true?"Beim Bericht OK":scanner===false?"Prüfung fehlgeschlagen":"Nicht belegt"};
 if(negative)return {...result,tone:"bad",label:stale?"Letzter Bericht: Störung – aktueller Status unklar":"Betriebsstörung gemeldet",note:stale?"Letzter negativer Beleg bleibt sichtbar. Keine aktuelle Entwarnung.":writer===false?"V3-Writer-Prüfung fehlgeschlagen. Betriebszustand beim Originalhost klären.":scanner===false?"Scanner-Prüfung fehlgeschlagen.":"Mini-PC meldet kritischen Fehler."};
 if(stale)return {...result,tone:"unknown",label:"Systemstatus nicht aktuell",note:!connected?"Cloud-Verbindung nicht bestätigt.":elapsedSec>CLOUD_RESPONSE_STALE_SEC?"Cloud-Abfrage überfällig.":"Hostbericht älter als fünf Minuten."};
 if(age>HOST_REPORT_DUE_SEC)return {...result,tone:"warn",label:"Neuer Hostbericht fällig",note:"Hostbericht älter als drei Minuten. Letzte Befunde bleiben sichtbar; aktuelle Gesundheit nicht bestätigt."};
 if(h.status==="WARNING"||issues.some(i=>i?.severity==="WARNING")){
  const core=active&&writer===true&&scanner===true;
  return {...result,tone:"warn",label:core?"Writer und Scanner bestätigt – Systemwarnung":"Systemwarnung gemeldet",note:core?"Die Kernprüfungen waren beim letzten Bericht positiv. Weitere Hostwarnungen sind separat zu klären; kein Writer-Ausfall daraus ableiten.":"Mindestens eine Hostprüfung meldet eine Warnung."};
 }
 if(!active||writer!==true||scanner!==true||h.status!=="HEALTHY"||!Array.isArray(h.issues))return {...result,tone:"unknown",label:"Gesundheit nicht vollständig belegt",note:"Aktive Serie, Scanner, Writer und Hoststatus müssen eindeutig bestätigt sein."};
 return {...result,tone:"good",label:"System beim letzten Bericht gesund",note:"Scanner und Writer bestätigt. Zeitgestempelter Nachweis, keine Echtzeitgarantie."};
}
let healthReceiptMs=null,healthConnected=false,healthLastPollMs=null;
function healthReset(){healthReceiptMs=null;healthConnected=false;healthLastPollMs=null;$('health-banner').hidden=true;closeHealthDetails();$('health-details-list').replaceChildren();delete $('health-details-list').dataset.key;$('health-details-time').textContent='';}
function healthReceived(){healthReceiptMs=Date.now();healthConnected=true;paintHealth();}
function healthFailed(){healthConnected=false;paintHealth();}
function paintHealth(){
 const box=$('health-banner');if(!data){box.hidden=true;paintIncident();return;}box.hidden=false;
 const elapsed=healthReceiptMs===null?NaN:(Date.now()-healthReceiptMs)/1000;
 const m=healthModel(data,elapsed,healthConnected);
 box.dataset.tone=m.tone;
 const title=$('health-title');if(title.textContent!==m.label)title.textContent=m.label;
 $('health-note').textContent=m.note;
 const age=m.hostAge===null?'nicht belegt':m.hostAge<60?m.hostAge+' Sek.':Math.floor(m.hostAge/60)+' Min. '+(m.hostAge%60)+' Sek.';
 $('health-age').textContent='Hostbericht: '+age+' alt · '+(m.hostAt?time(m.hostAt):'Zeit nicht belegt');
 $('health-writer').textContent='Writer: '+m.writer;$('health-scanner').textContent='Scanner: '+m.scanner;renderHealthDetails(m);paintIncident();
}
function healthTick(){
 if(document.hidden||!access)return;
 paintHealth();
 if(healthLastPollMs===null||Date.now()-healthLastPollMs>=30000)refresh();
}
window.addEventListener('offline',healthFailed);
window.addEventListener('online',()=>{if(!document.hidden&&access)refresh();});
function closeHealthDetails(){
 const button=$('health-details');button.setAttribute('aria-expanded','false');button.textContent='Details';$('health-details-content').hidden=true;
}
function renderHealthDetails(m){
 const box=$('health-details-list'),hosts=Array.isArray(data?.hosts)?data.hosts.filter(h=>h?.node_id==='MINI-PC'):[],h=hosts.length===1?hosts[0]:null;
 const issues=Array.isArray(h?.issues)?h.issues.slice(0,30):[];
 const labels={v3_paper_single_writer:'V3-Writer',runtime_supervisor:'Laufzeitüberwachung',kraken_universe_heartbeat:'Kraken-Scanner',minipc_status_sync:'Statusübertragung',v2r4_ws_shadow_outcomes:'V2R4-Nachbetrachtung',v2r4_paper_wait:'V2R4-Warteüberwachung',v2r4_paper_candidates:'V2R4-Kandidaten'};
 const list=issues.map(i=>({label:labels[i?.check]||(/^[a-z0-9_]{1,80}$/i.test(i?.check||'')?i.check:'Weitere Hostprüfung'),severity:['WARNING','CRITICAL'].includes(i?.severity)?i.severity:'Nicht eingeordnet',detail:typeof i?.detail==='string'?i.detail.slice(0,500):'Kein Detail übermittelt.'}));
 const key=JSON.stringify([m.label,m.note,h?.observed_at,list]);
 if(box.dataset.key===key)return;
 box.dataset.key=key;$('health-details-time').textContent='Hostbericht: '+time(h?.observed_at)+' · '+m.label;
 box.replaceChildren(el('p',m.note,'sub'),...list.map(i=>{const row=el('div',undefined,'health-detail-row');row.append(el('strong',i.label+' · '+(i.severity==='WARNING'?'Warnung':i.severity==='CRITICAL'?'Kritisch':i.severity)),el('p',i.detail));return row;}));
 if(!list.length)box.append(el('p','Keine einzelnen Warnungen im vorhandenen Bericht übermittelt. Keine zusätzliche Ursachenfeststellung.','sub'));
}
$('health-details').addEventListener('click',()=>{
 if(!data)return;
 if(!$('health-details-content').hidden){closeHealthDetails();return;}
 const button=$('health-details');$('health-details-content').hidden=false;button.setAttribute('aria-expanded','true');button.textContent='Schließen';paintHealth();
});
