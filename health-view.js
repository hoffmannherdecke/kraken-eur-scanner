'use strict';
// Accept only an explicit allowlisted classification from the original-host watchdog.
function supervisorProtection(issues){
 if(!Array.isArray(issues))return false;
 const rows=issues.filter(i=>i?.check==="runtime_supervisor");
 if(rows.length!==1||rows[0].severity!=="WARNING"||typeof rows[0].detail!=="string")return false;
 const m=rows[0].detail.match(/^status=WARNING age_sec=(\d{1,3}(?:[.,]\d{1,6})?) restarted= classification=EXPECTED_V3_FENCE_ONLY_V1$/);
 return !!m&&Number(m[1].replace(",","."))<=300;
}
// Distinct positive protection evidence with a bounded research delay, not fence-only.
function supervisorResearchDelay(issues){
 if(!Array.isArray(issues))return false;
 const rows=issues.filter(i=>i?.check==="runtime_supervisor");
 if(rows.length!==1||rows[0].severity!=="WARNING"||typeof rows[0].detail!=="string")return false;
 const m=rows[0].detail.match(/^status=WARNING age_sec=(\d{1,3}(?:[.,]\d{1,6})?) restarted= classification=EXPECTED_V3_FENCE_WITH_RESEARCH_DELAY_V1$/);
 return !!m&&Number(m[1].replace(",","."))<=300;
}
function boundedShadowDelay(issues){
 const rows=issues.filter(i=>i?.check==="v2r4_ws_shadow_outcomes");
 if(rows.length!==1||rows[0].severity!=="WARNING"||typeof rows[0].detail!=="string")return false;
 const m=rows[0].detail.match(/^status=HEALTHY age_sec=(\d{1,3}(?:[.,]\d{1,6})?) active=(\d{1,9}) sampled_active=(\d{1,9}) recent_active_samples=(\d{1,9}) freshest_active_sample_age_sec=(\d{1,3}(?:[.,]\d{1,6})?) oldest_active_sample_age_sec=(\d{1,3}(?:[.,]\d{1,6})?) enrolled=(\d{1,12}) completed=(\d{1,12})$/);
 if(!m)return false;
 const [age,active,sampled,recent,freshest,oldest,enrolled,completed]=m.slice(1).map(x=>Number(x.replace(",",".")));
 return age>60&&age<=300&&active>0&&sampled===active&&recent===active&&freshest>=0&&freshest<=oldest&&oldest<=300&&completed<=enrolled&&active<=enrolled;
}
// UI-only advisory classification. No change to the original watchdog or its limits.
// Require a complete, narrowly bounded positive research sample summary.
function shadowResearchAdvisory(issues){
 if(!Array.isArray(issues))return false;
 const rows=issues.filter(i=>i?.check==="v2r4_ws_shadow_outcomes");
 if(rows.length!==1||rows[0].severity!=="WARNING"||typeof rows[0].detail!=="string")return false;
 const m=rows[0].detail.match(/^status=HEALTHY age_sec=(\d{1,3}(?:[.,]\d{1,6})?) active=(\d{1,9}) sampled_active=(\d{1,9}) recent_active_samples=(\d{1,9}) freshest_active_sample_age_sec=(\d{1,3}(?:[.,]\d{1,6})?) oldest_active_sample_age_sec=(\d{1,3}(?:[.,]\d{1,6})?) enrolled=(\d{1,12}) completed=(\d{1,12})$/);
 if(!m)return false;
 const [age,active,sampled,recent,freshest,oldest,enrolled,completed]=m.slice(1).map(x=>Number(x.replace(",",".")));
 return age>=0&&age<=60&&active>0&&sampled===active&&recent>0&&recent<=sampled&&freshest<=60&&freshest<=oldest&&completed<=enrolled&&active<=enrolled;
}
function supervisorCritical(issues){
 return issues.some(i=>i?.check==="runtime_supervisor"&&typeof i.detail==="string"&&/^status=CRITICAL age_sec=/.test(i.detail));
}
function healthModel(v,elapsedSec,connected){
 const unknown=(label,note)=>({tone:"unknown",label,note,hostAge:null,hostAt:null,writer:"Unbekannt",scanner:"Unbekannt"});
 if(!v||!Array.isArray(v.hosts)||!Number.isFinite(elapsedSec)||elapsedSec<0)return unknown("Systemstatus nicht bekannt","Noch kein bestätigter Betriebsbericht.");
 const hosts=v.hosts.filter(h=>h?.node_id==="MINI-PC");
 if(hosts.length!==1)return unknown("Mini-PC nicht eindeutig belegt","Kein eindeutiger Originalhost-Bericht.");
 const h=hosts[0],read=Date.parse(v.read_at),observed=Date.parse(h.observed_at),baseAge=(read-observed)/1000;
 if(!Number.isFinite(baseAge)||baseAge< -30)return unknown("Systembericht zeitlich unklar","Zeitstempel fehlen oder sind widersprüchlich.");
 const age=Math.max(0,baseAge+elapsedSec),issues=Array.isArray(h.issues)?h.issues:[],writerIssue=issues.find(i=>i?.check==="v3_paper_single_writer");
 const writer=h.writer?.ok===false||writerIssue?false:h.writer?.ok===true?true:null,scanner=h.scanner_ok===true?true:h.scanner_ok===false?false:null;
 const critical=h.status==="CRITICAL"||issues.some(i=>i?.severity==="CRITICAL")||supervisorCritical(issues),negative=critical||writer===false||scanner===false;
 const stale=!connected||elapsedSec>CLOUD_RESPONSE_STALE_SEC||age>HOST_REPORT_STALE_SEC;
 const active=Array.isArray(v.series)&&v.series.length===1&&v.series[0]?.status==="active";
 const levelMatch=active&&/^PAPER-V3-\d{8}T\d{6}Z$/.test(v.series[0]?.series_id||"")&&
  !stale&&age<=HOST_REPORT_DUE_SEC&&typeof h.writer?.detail==="string"?
  /^local task\/process\/heartbeat match=(True|False) age_sec=-?\d{1,3}(?:[.,]\d{1,6})? operating_level=([123])$/.exec(h.writer.detail):null;
 const level=levelMatch&&(levelMatch[1]==="True"&&writer===true&&levelMatch[2]!=="3"||
  levelMatch[1]==="False"&&h.writer.ok===false&&levelMatch[2]==="3"&&writerIssue?.severity==="WARNING"&&
  writerIssue.detail===h.writer.detail)?Number(levelMatch[2]):null;
 const levelLabel={1:"Stufe 1 · Normalbetrieb",2:"Stufe 2 · Warnung",3:"Stufe 3 · Eingeschränkter Betrieb"}[level];
 const result={hostAge:Math.floor(age),hostAt:h.observed_at,writer:levelLabel??(writer===true?"Beim Bericht OK":writer===false?"Prüfung fehlgeschlagen":"Nicht belegt"),scanner:scanner===true?"Beim Bericht OK":scanner===false?"Prüfung fehlgeschlagen":"Nicht belegt"};
 if(level===3&&!critical&&scanner===true)return {...result,tone:"warn",label:"V3-Paper-Betrieb eingeschränkt",note:"Eine Writer-Teilfunktion pausiert. Die gemeldeten Hostbefunde stehen unter Details."};
 const diagnosis=h.writer?.diagnosis;
 const holdAt=Date.parse(diagnosis?.checked_at_utc);
 const holdAge=(observed-holdAt)/1000;
 if(!critical&&!stale&&age<=HOST_REPORT_DUE_SEC&&active&&writer===false&&h.writer?.ok===false&&
    diagnosis?.series_id===v.series[0].series_id&&/^HOLD_[A-Z0-9_]{1,100}$/.test(diagnosis.cycle_status)&&
    Number.isFinite(holdAge)&&holdAge>=-30&&holdAge<=180){
  return {...result,tone:"bad",writer:"Writer-HOLD bestätigt",label:"V3-Writer gestoppt",note:"Der Originalhost meldet einen Stopp für die aktive Serie. Der konkrete Befund steht unter Details."};
 }
 const fenceStopRequired=!stale&&age<=HOST_REPORT_DUE_SEC&&issues.some(i=>
  i?.check==="runtime_supervisor"&&i.severity==="WARNING"&&typeof i.detail==="string"&&
  /^status=CRITICAL age_sec=.* classification=V3_SECURITY_STOP_REQUIRED_PREDECESSOR_FENCE$/.test(i.detail));
 if(fenceStopRequired)return {...result,tone:"bad",label:"Stufe 4 · Sicherheitsstopp erforderlich",note:"Der Supervisor meldet eine aktivierte Vorgänger-Task trotz produktiver Sperre. Der Stopp muss am Originalhost bestätigt werden."};
 if(negative)return {...result,tone:"bad",label:stale?"Letzter Bericht: Störung – aktueller Status unklar":"Betriebsstörung gemeldet",note:stale?"Letzter negativer Beleg bleibt sichtbar. Keine aktuelle Entwarnung.":writer===false?"V3-Writer-Prüfung fehlgeschlagen. Betriebszustand beim Originalhost klären.":scanner===false?"Scanner-Prüfung fehlgeschlagen.":"Mini-PC meldet kritischen Fehler."};
 if(stale)return {...result,tone:"unknown",label:"Systemstatus nicht aktuell",note:!connected?"Cloud-Verbindung nicht bestätigt.":elapsedSec>CLOUD_RESPONSE_STALE_SEC?"Cloud-Abfrage überfällig.":"Hostbericht älter als fünf Minuten."};
 if(age>HOST_REPORT_DUE_SEC)return {...result,tone:"warn",label:"Neuer Hostbericht fällig",note:"Hostbericht älter als drei Minuten. Letzte Befunde bleiben sichtbar; aktuelle Gesundheit nicht bestätigt."};
 const researchDelayProtected=active&&/^PAPER-V3-\d{8}T\d{6}Z$/.test(v.series[0]?.series_id||"")&&writer===true&&scanner===true&&h.status==="WARNING"&&supervisorResearchDelay(issues);
 const separatedResearchDelay=researchDelayProtected&&boundedShadowDelay(issues)&&issues.length===2&&issues.every(i=>i?.check==="runtime_supervisor"||i?.check==="v2r4_ws_shadow_outcomes");
 const fenceProtected=active&&writer===true&&scanner===true&&h.status==="WARNING"&&(supervisorProtection(issues)||researchDelayProtected);
 const shadowAdvisory=!researchDelayProtected&&active&&/^PAPER-V3-\d{8}T\d{6}Z$/.test(v.series[0]?.series_id||"")&&writer===true&&scanner===true&&h.status==="WARNING"&&shadowResearchAdvisory(issues)&&issues.length===(fenceProtected?2:1)&&issues.every(i=>i?.check==="v2r4_ws_shadow_outcomes"||(fenceProtected&&i?.check==="runtime_supervisor"));
 if(level===2&&scanner===true)return {...result,tone:"warn",fenceProtected,shadowAdvisory,label:"V3-Paper-Betrieb aktiv · Warnung",note:"Eine Verarbeitung wurde zurückgestellt. Weitere Hostbefunde stehen unter Details."};
 if(separatedResearchDelay)return {...result,tone:"good",fenceProtected:true,shadowAdvisory:true,label:"V3-Paper-Betrieb aktiv",note:"Writer und Scanner beim letzten Bericht bestätigt. Separater verzögerter Forschungszyklus unter Details; Originalwarnung bleibt erhalten. Keine Echtzeitgarantie."};
 if(shadowAdvisory)return {...result,tone:"good",fenceProtected,shadowAdvisory:true,label:"V3-Paper-Betrieb aktiv",note:"Writer und Scanner beim letzten Bericht bestätigt. Separater Forschungshinweis unter Details; Originalwarnung bleibt erhalten. Keine Echtzeitgarantie."};
 if(fenceProtected&&!researchDelayProtected&&issues.length===1)return {...result,tone:"good",fenceProtected:true,label:"V3-Paper-Betrieb aktiv",note:"Vorgänger-Writer geschützt. Writer und Scanner beim letzten Bericht bestätigt. Kein Reparaturbedarf aus diesem Schutzbefund; keine Echtzeitgarantie."};
 if(fenceProtected)return {...result,tone:"warn",fenceProtected:true,label:"Sicherheitsmechanismus aktiv – weitere Systemwarnung",note:"Vorgänger-Writer geschützt. Weitere Hostwarnungen separat prüfen."};
 if(h.status==="WARNING"||issues.some(i=>i?.severity==="WARNING")){
  const core=active&&writer===true&&scanner===true;
  return {...result,tone:"warn",label:core?"Writer und Scanner bestätigt – Systemwarnung":"Systemwarnung gemeldet",note:core?"Die Kernprüfungen waren beim letzten Bericht positiv. Weitere Hostwarnungen sind separat zu klären; kein Writer-Ausfall daraus ableiten.":"Mindestens eine Hostprüfung meldet eine Warnung."};
 }
 if(!active||writer!==true||scanner!==true||h.status!=="HEALTHY"||!Array.isArray(h.issues))return {...result,tone:"unknown",label:"Gesundheit nicht vollständig belegt",note:"Aktive Serie, Scanner, Writer und Hoststatus müssen eindeutig bestätigt sein."};

 return {...result,tone:"good",label:"V3-Paper-Betrieb aktiv",note:"Scanner und Writer bestätigt. Zeitgestempelter Nachweis, keine Echtzeitgarantie."};
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
 const list=issues.map(i=>({label:m.fenceProtected&&i?.check==='runtime_supervisor'?'Sicherheitsmechanismus aktiv':m.shadowAdvisory&&i?.check==='v2r4_ws_shadow_outcomes'?'Forschungshinweis (V2R4)':labels[i?.check]||(/^[a-z0-9_]{1,80}$/i.test(i?.check||'')?i.check:'Weitere Hostprüfung'),severity:m.fenceProtected&&i?.check==='runtime_supervisor'?'Schutz bestätigt':m.shadowAdvisory&&i?.check==='v2r4_ws_shadow_outcomes'?'Separate Originalwarnung':['WARNING','CRITICAL'].includes(i?.severity)?i.severity:'Nicht eingeordnet',detail:m.fenceProtected&&i?.check==='runtime_supervisor'?'Vorgänger-Writer geschützt. Kein Reparaturbedarf aus diesem Befund.':typeof i?.detail==='string'?i.detail.slice(0,500):'Kein Detail übermittelt.'}));
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
