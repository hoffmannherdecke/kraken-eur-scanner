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
 const stale=!connected||elapsedSec>75||age>600;
 const active=Array.isArray(v.series)&&v.series.length===1&&v.series[0]?.status==="active";
 const result={hostAge:Math.floor(age),hostAt:h.observed_at,writer:writer===true?"Beim Bericht OK":writer===false?"Prüfung fehlgeschlagen":"Nicht belegt",scanner:scanner===true?"Beim Bericht OK":scanner===false?"Prüfung fehlgeschlagen":"Nicht belegt"};
 if(negative)return {...result,tone:"bad",label:stale?"Letzter Bericht: Störung – aktueller Status unklar":"Betriebsstörung gemeldet",note:stale?"Letzter negativer Beleg bleibt sichtbar. Keine aktuelle Entwarnung.":writer===false?"V3-Writer-Prüfung fehlgeschlagen. Betriebszustand beim Originalhost klären.":scanner===false?"Scanner-Prüfung fehlgeschlagen.":"Mini-PC meldet kritischen Fehler."};
 if(stale)return {...result,tone:"unknown",label:"Systemstatus nicht aktuell",note:!connected?"Cloud-Verbindung nicht bestätigt.":elapsedSec>75?"Cloud-Abfrage überfällig.":"Hostbericht älter als 10 Minuten."};
 if(h.status==="WARNING"||issues.some(i=>i?.severity==="WARNING"))return {...result,tone:"warn",label:"Systemwarnung gemeldet",note:"Mindestens eine Hostprüfung meldet eine Warnung."};
 if(!active||writer!==true||scanner!==true||h.status!=="HEALTHY"||!Array.isArray(h.issues))return {...result,tone:"unknown",label:"Gesundheit nicht vollständig belegt",note:"Aktive Serie, Scanner, Writer und Hoststatus müssen eindeutig bestätigt sein."};
 if(age>360)return {...result,tone:"warn",label:"Letzter Bericht gesund – neuer Bericht fällig",note:"Hostbericht älter als sechs Minuten; erneute Bestätigung ausstehend."};
 return {...result,tone:"good",label:"System beim letzten Bericht gesund",note:"Scanner und Writer bestätigt. Zeitgestempelter Nachweis, keine Echtzeitgarantie."};
}
let healthReceiptMs=null,healthConnected=false,healthLastPollMs=null;
function healthReset(){healthReceiptMs=null;healthConnected=false;healthLastPollMs=null;$('health-banner').hidden=true;}
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
 $('health-writer').textContent='Writer: '+m.writer;$('health-scanner').textContent='Scanner: '+m.scanner;paintIncident();
}
function healthTick(){
 if(document.hidden||!access)return;
 paintHealth();
 if(healthLastPollMs===null||Date.now()-healthLastPollMs>=30000)refresh();
}
window.addEventListener('offline',healthFailed);
window.addEventListener('online',()=>{if(!document.hidden&&access)refresh();});
$('health-details').addEventListener('click',()=>document.querySelector('nav button[data-page="system"]').click());
