'use strict';
function incidentContext(v,elapsed,connected,now=Date.now()){
 if(!v||!Number.isFinite(now)||!Number.isFinite(elapsed)||elapsed<0||!Number.isFinite(Date.parse(v.read_at))||Date.parse(v.read_at)>now+30000)return null;
 const s=Array.isArray(v.series)&&v.series.length===1&&v.series[0]?.status==="active"&&/^PAPER-V3-\d{8}T\d{6}Z$/.test(v.series[0].series_id)?v.series[0].series_id:null;
 const m=healthModel(v,elapsed,connected);
 if(m.tone==="good"&&now-Date.parse(v.read_at)<=180000)return null;
 const hs=Array.isArray(v.hosts)?v.hosts.filter(h=>h?.node_id==="MINI-PC"):[];
 const h=hs.length===1?hs[0]:null;
 const at=h&&Number.isFinite(Date.parse(h.observed_at))&&Date.parse(h.observed_at)<=Date.parse(v.read_at)+30000?new Date(Date.parse(h.observed_at)).toISOString():null;
 const issues=Array.isArray(h?.issues)?h.issues:[];
 const codes=[];
 if(h?.writer?.ok===false||issues.some(i=>i?.check==="v3_paper_single_writer"))codes.push("WRITER_CHECK_FAILED");
 if(h?.scanner_ok===false)codes.push("SCANNER_CHECK_FAILED");
 if(!m.fenceProtected&&issues.some(i=>i?.check==="runtime_supervisor"&&["WARNING","CRITICAL"].includes(i.severity)))codes.push("SUPERVISOR_WARNING");
 if(h?.status==="CRITICAL"||issues.some(i=>i?.severity==="CRITICAL")||supervisorCritical(issues))codes.push("HOST_CRITICAL");
 else if((h?.status==="WARNING"&&!m.fenceProtected)||issues.some(i=>i?.severity==="WARNING"&&!(m.fenceProtected&&i.check==="runtime_supervisor")))codes.push("HOST_WARNING");
 if(!connected||elapsed>CLOUD_RESPONSE_STALE_SEC||now-Date.parse(v.read_at)>180000)codes.push("CLOUD_READ_NOT_CURRENT");
 const exactHostAge=at?(Date.parse(v.read_at)-Date.parse(at))/1000+elapsed:NaN;
 if(!Number.isFinite(exactHostAge)||m.hostAge===null||exactHostAge>HOST_REPORT_DUE_SEC)codes.push("HOST_REPORT_NOT_CURRENT");
 if(!s)codes.push("ACTIVE_SERIES_UNCONFIRMED");
 if(!codes.length)codes.push("HEALTH_NOT_CONFIRMED");
 const readAt=new Date(Date.parse(v.read_at)).toISOString();
 const current=!!connected&&elapsed<=CLOUD_RESPONSE_STALE_SEC&&now-Date.parse(v.read_at)<=180000&&!!at&&m.hostAge!==null&&exactHostAge<=HOST_REPORT_STALE_SEC;
 const ctx={series:s,hostAt:at,readAt,codes,tone:m.tone,current};
 ctx.diagnostics=incidentDiagnostics(v,ctx);
 ctx.key=JSON.stringify([s,at,codes,current,m.tone,ctx.diagnostics]);
 return ctx;
}
function incidentDiagnostics(v,ctx){
 if(!ctx||!ctx.hostAt||!Array.isArray(v?.hosts))return [];
 const hs=v.hosts.filter(h=>h?.node_id==="MINI-PC");
 if(hs.length!==1||Date.parse(hs[0].observed_at)!==Date.parse(ctx.hostAt))return [];
 const h=hs[0],issues=Array.isArray(h.issues)?h.issues:[],out=[];
 const age=x=>{if(typeof x!=="string"||! /^-?\d{1,9}(?:[.,]\d{1,6})?$/.test(x))return null;const n=Number(x.replace(",","."));return Number.isFinite(n)&&Math.abs(n)<=315360000?n:null;};
 const add=(code,label,value,next)=>out.push({code,label,value,next});
 const issue=key=>{const a=issues.filter(i=>i?.check===key);return a.length===1?a[0]:null;};
 const wi=issue("v3_paper_single_writer"),w=h.writer;
 if(ctx.codes.includes("WRITER_CHECK_FAILED")){
 const raw=w?.detail,other=wi?.detail;
 const m=typeof raw==="string"&&raw.length<=500&&raw.match(/^local task\/process\/heartbeat match=(True|False) age_sec=(-?\d{1,9}(?:[.,]\d{1,6})?)$/i),n=m?age(m[2]):null;
 const consistent=w?.ok===false&&issues.filter(i=>i?.check==="v3_paper_single_writer").length<=1&&(!wi||other===raw);

 const d=w?.diagnosis;
 if(consistent&&d&&d.series_id===ctx.series){
   add("WRITER_ORIGINAL_HOLD","Writer-HOLD",d.cycle_status+" · "+d.checked_at_utc,"Seriengebundenen Originalbefund mit dem installierten Launcher und aktuellen Owner-Verträgen abgleichen.");
   const f=d.failure_detail,s=d.failure_site;
   if(f)add("WRITER_ORIGINAL_CATEGORY","Fehlerkategorie",[f.category,f.reported_code,f.returncode].filter(x=>x!==undefined).join(" · "),"Den gemeldeten Fehlercode am Originalquellstand prüfen und mit dem auslösenden Befund verbinden.");
   if(s)add("WRITER_ORIGINAL_SITE","Fehlerstelle",s.file+" · "+s.function+" · Zeile "+s.line,"Die Stelle gegen den zum Vorfall gehörenden Quellstand prüfen.");
   add("WRITER_ORIGINAL_IDENTITY","Quell- und Laufzeitbindung",[d.release_repo_sha,d.runtime_bundle_sha256,d.strategy_sha256].join(" · "),"Installierte Version und aktuellen main abgleichen, bevor eine Korrektur vorbereitet wird.");
 }
 if(m&&n!==null&&m[1].toLowerCase()==="false"&&consistent){
 add("WRITER_COMPOSITE","Writer-Gesamtprüfung","Nicht bestanden; Heartbeat-Alter beim Hostcheck: "+n+" s.","Task, Prozess, Heartbeat, Identität, Fence und Lease werden gemeinsam geprüft. Ersten tatsächlich fehlerhaften Teilbefund und ursprüngliche Ausnahme am Originalhost ermitteln.");
 if(n>180)add("WRITER_HEARTBEAT_OLD","Writer-Heartbeat","Älter als die ursprüngliche 180-s-Prüfgrenze.","Letzten ursprünglichen Writer-Lauf, Zeitstempel und Abbruch-/HOLD-Belege prüfen. Kein Neustart aus dem Symptom ableiten.");
 else if(n< -30)add("WRITER_HEARTBEAT_FUTURE","Writer-Heartbeat","Außerhalb der ursprünglichen negativen Altersgrenze von -30 s.","Originale Zeitstempel und konkrete Frischeprüfung untersuchen. Keine Uhrverstellung oder Toleranzänderung ableiten.");
 }else if(consistent&&raw==="fence present but not a valid committed successor")add("WRITER_FENCE_OBSERVATION","Writer-Fence","Watchdog meldet keine gültige committed successor-Bindung.","Originale Fence-/Serienbindung lesend prüfen. Kein Fence-Eingriff, kein CAS.");
 else if(consistent&&raw==="V3 local successor observation unavailable")add("WRITER_OBSERVATION_UNAVAILABLE","Writer-Beobachtung","Lokale Nachfolgerbeobachtung nicht verfügbar.","Vorhandene Originalhost-Readbacks und Fehlerprotokolle der fehlgeschlagenen Beobachtung prüfen.");
 else add("WRITER_DETAIL_UNCONFIRMED","Writer-Details","Nicht eindeutig strukturiert oder widersprüchlich.","Originalen Watchdog-Befund, Task-Readback, Heartbeat und zugehöriges Writer-Fehlerprotokoll lesend abgleichen.");
 }
 if(ctx.codes.includes("SUPERVISOR_WARNING")){
 const raw=issue("runtime_supervisor")?.detail,m=typeof raw==="string"&&raw.length<=500&&raw.match(/^status=(HEALTHY|WARNING|CRITICAL|ERROR|FAILED|UNKNOWN) age_sec=(-?\d{1,9}(?:[.,]\d{1,6})?) restarted=([^\r\n]*)$/),n=m?age(m[2]):null;
 if(m&&n!==null){add("SUPERVISOR_OBSERVATION","Supervisor","Status "+m[1]+"; Berichtsalter beim Hostcheck: "+n+" s. "+(m[3]===""?"Restart-Liste im Bericht leer.":"Restart-Angaben nicht übernommen."),"Ursprünglichen Supervisor-Zustand prüfen: Fence-Modus, Nachfolgerbindung, Maintenance, failed_restarts, error und alle überwachten Tasks. CLOUD_COMMITTED kann eine erwartete Schutzwarnung sein; dieser kompakte Bericht unterscheidet das nicht sicher. Keine Reparatur oder Unterdrückung daraus ableiten.");
 if(n>300)add("SUPERVISOR_OLD","Supervisor-Bericht","Älter als die ursprüngliche 300-s-Prüfgrenze.","Zeitstempel und Original-Supervisor-Meldung prüfen.");}
 else if(raw==="task installed but state missing")add("SUPERVISOR_STATE_MISSING","Supervisor-Zustand","Task installiert, Zustandsdatei laut Watchdog fehlt.","Vorhandenen Supervisor-Task und Original-Zustandsbeleg lesend prüfen.");
 else add("SUPERVISOR_DETAIL_UNCONFIRMED","Supervisor-Details","Kein eindeutig strukturiertes Detail verfügbar.","Originalen Supervisor-Bericht und zugehörige Warnung lesend prüfen.");
 }
 if(ctx.codes.includes("SCANNER_CHECK_FAILED"))add("SCANNER_OBSERVATION","Scanner","Kraken-EUR-Universe-Prüfung meldet einen Fehler.","Originalen Universe-Heartbeat, Verbindungszustand, Ticker-Alter, Paarabdeckung und Subscription-Fehler prüfen.");
 if(issues.some(i=>i?.check==="minipc_status_sync"&&["WARNING","CRITICAL"].includes(i.severity)))add("SYNC_OBSERVATION","Statusübertragung","StatusSync-Prüfung meldet einen Fehler.","Vorhandenen StatusSync-Heartbeat und Relay-Fehlerbeleg lesen. Keine neuen Übertragungswege oder Rechte.");
 if(ctx.codes.includes("HOST_REPORT_NOT_CURRENT")||ctx.codes.includes("CLOUD_READ_NOT_CURRENT"))add("FRESHNESS","Aktualität","Befund ist nicht als aktueller Live-Zustand bestätigt.","Zuerst neueren Originalhost-/Cloud-Nachweis beschaffen; keine Reparatur aus altem Bericht auslösen.");
 return out;
}
function incidentDraft(ctx){
 if(!ctx)return null;
 const labels={WRITER_CHECK_FAILED:"Writer-Prüfung fehlgeschlagen",SCANNER_CHECK_FAILED:"Scanner-Prüfung fehlgeschlagen",SUPERVISOR_WARNING:"Supervisor meldet Warnung",HOST_CRITICAL:"Kritischer Hostbericht",HOST_WARNING:"Hostwarnung",CLOUD_READ_NOT_CURRENT:"Cloud-Abruf nicht aktuell",HOST_REPORT_NOT_CURRENT:"Hostbericht überfällig oder zeitlich nicht belegt",ACTIVE_SERIES_UNCONFIRMED:"Aktive V3-Serie nicht eindeutig",HEALTH_NOT_CONFIRMED:"Systemgesundheit nicht bestätigt"};
 if(!Array.isArray(ctx.codes)||!ctx.codes.length||!ctx.codes.every(c=>Object.hasOwn(labels,c)))return null;
 return [
 "KRYPTO-V3 – Störungsaufnahme und gezielte Fortsetzung",
 "",
 "Repository: hoffmannherdecke/kraken-eur-scanner",
 "Projektmanager: https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/353",
 "V3-Fachowner: https://github.com/hoffmannherdecke/kraken-eur-scanner/issues/99",
 "App-Abruf UTC: "+ctx.readAt,
 "Originalhost-Berichtszeit UTC: "+(ctx.hostAt||"Nicht bestätigt"),
 "Serie laut App: "+(ctx.series||"Nicht eindeutig bestätigt"),
 "Aktualität: "+(ctx.current?"Letzter zeitgestempelter Cloud-/Hostbericht, kein Echtzeitbeweis":"Nicht aktuell oder nicht eindeutig; nur letzter Anhaltspunkt"),
 "Gemeldete Befunde: "+ctx.codes.map(c=>labels[c]).join("; "),
 "",
 "Strukturierte Original-Watchdog-Details (nur Befunde, keine Ursachenfeststellung):",
 ...(ctx.diagnostics||[]).map(d=>"- "+d.label+": "+d.value+" Gezielte Originalprüfung: "+d.next),
 "Lokale Detailprotokolle: noch nicht ausgelesen. Im zuständigen Arbeitsauftrag zuerst bereits verfügbare Originalfehlerprotokolle und Readbacks übernehmen. Nur bei konkreter Lücke vorhandenen freigegebenen lesenden Mini-PC-Zugriff nutzen. Keine pauschale Logsammlung, keine Rechteerweiterung, keine Rohdaten in öffentliche GitHub-Kommentare. Bestehender log_status_summary liefert begrenzte Statuszahlen, keine vollständige Exception oder Ursachenbestätigung.",
 "",
 "Verbindlicher Arbeitsauftrag:",
 "1. Zuerst aktuellen geschützten main, AGENTS.md, #353, #99 und jüngste passende Originalhost-/Cloud-/Notebook-Nachweise prüfen. App-Befund ist keine Ursachenfeststellung und keine Ausführungsfreigabe.",
 "2. Bestehenden zuständigen Störungs-/Arbeitsauftrag und schon abgeschlossene Maßnahmen ermitteln. Falls bereits eine passende Reparatur läuft, ausschließlich dort fortsetzen; keine zweite Reparatur, kein weiterer Scheduler, kein neuer Manager. Ist der Befund inzwischen behoben, aktuellen Originalnachweis übernehmen und keine Reparatur auslösen.",
 "3. Tatsächliche Fehlerursache anhand der Originale eingrenzen. Nur die kleinste notwendige Korrektur im vorhandenen Vertrag entwickeln und isoliert die unmittelbar betroffenen Schnittstellen testen. Bereits gültige PASS-Nachweise nicht wiederholen.",
 "4. Bei notwendiger produktiver Änderung exakte Dateien, Identitäten, Testnachweise, Rollback und erforderliche persönliche Ownerfreigabe vorbereiten. Ohne die konkrete gültige Freigabe keine produktive Mutation, kein STOP/Start/CAS, keine Lease-/Fingerprints-/Rechteänderung, kein automatischer Restart und kein Echtgeld. Die App-Vorbereitung ist keine Freigabe.",
 "5. Nur nach nachgewiesener Autorisierung im zuständigen Arbeitsauftrag ausführen und anschließend tatsächliche Originalhost-/Cloud-Betriebswirkung nachweisen. Source/Tests, Freigabe, Installation und Betriebsabnahme getrennt dokumentieren. Kein grüner Betrieb allein aus einem GitHub-/CI-Beleg ableiten.",
 "6. Ergebnis im bestehenden zuständigen Owner-Vorgang dokumentieren: tatsächliche Ursache, Maßnahme, Tests, verbleibendes Gate oder bestätigter Originalbetriebsnachweis. Keine zusätzlichen Kosten.",
 "",
 "Leitfrage: Dient die Maßnahme dem zuverlässigen, wirtschaftlich erfolgreichen Handelsbetrieb, seiner gezielten Weiterentwicklung oder der notwendigen Vorbereitung des Echtgeldbetriebs?"
 ].join("\n");
}
let incidentPrepared=null;
function clearIncident(message='Noch kein Störungsauftrag vorbereitet.'){
 incidentPrepared=null;$('incident-draft').value='';$('incident-draft').hidden=true;$('incident-copy').disabled=true;$('incident-open-work').hidden=true;$('incident-prepared').textContent='Nicht vorbereitet';$('incident-feedback').textContent=message;
}
function activeIncident(){
 if(!access||!data||$('login').hidden!==true||appSession&&appSession.expires<=Date.now())return null;
 const elapsed=healthReceiptMs===null?NaN:(Date.now()-healthReceiptMs)/1000;
 return incidentContext(data,elapsed,healthConnected);
}
function resetIncident(){
 clearIncident();$('incident-action').hidden=true;$('incident-create').disabled=true;$('incident-context').textContent='Noch kein bestätigter Cloud-Abruf.';$('incident-detected').textContent='Nicht belegt';$('incident-diagnostics').replaceChildren();
}
function paintIncident(){
 const ctx=activeIncident();
 $('incident-action').hidden=!ctx;
 $('incident-create').disabled=!ctx;
 $('incident-detected').textContent=ctx?'Abweichung / Klärungsbedarf':'Kein Störungsauftrag verfügbar';
 $('incident-context').textContent=ctx?'App-Abruf: '+time(ctx.readAt)+' · Hostbericht: '+time(ctx.hostAt)+' · '+(ctx.current?'Zeitgestempelter Befund':'Aktualität nicht bestätigt'):'Kein aktuell vorbereitbarer Störungsauftrag.';
 const lines=ctx?.diagnostics||[],diagnosticKey=JSON.stringify([!!ctx,lines]),box=$('incident-diagnostics');
 if(box.dataset.key!==diagnosticKey||(!box.childNodes.length&&lines.length)){box.dataset.key=diagnosticKey;box.replaceChildren(...(lines.length?lines.map(d=>{const p=el('div',undefined,'incident-detail');p.append(el('strong',d.label),el('p',d.value),el('small',d.next));return p;}):[el('p',ctx?'Die gemeldete Warnung ist noch nicht einer strukturierten Fehlerkategorie zugeordnet. Die konkreten Originalmeldungen stehen unter Details.':'Kein aktueller Störungsauftrag verfügbar.','sub')]));}
 if(incidentPrepared&&(!ctx||ctx.key!==incidentPrepared.key))clearIncident('Befund geändert oder nicht mehr verfügbar. Auftrag anhand der neuen Lage vorbereiten.');
}
$('incident-action').addEventListener('click',()=>{
 if(!activeIncident())return;
 closeHealthDetails();
 document.querySelector('nav button[data-page="system"]').click();
 const banner=$('health-banner'),target=$('incident-view');
 target.style.scrollMarginTop=Math.ceil(banner.getBoundingClientRect().height+Math.max(0,parseFloat(getComputedStyle(banner).top)||0)+12)+'px';
 requestAnimationFrame(()=>{if(!$('system').hidden&&activeIncident())target.scrollIntoView({block:'start',behavior:'auto'});});
});
$('incident-create').addEventListener('click',()=>{
 const ctx=activeIncident(),draft=incidentDraft(ctx);
 if(!draft){clearIncident('Keine eindeutige Störungsgrundlage.');paintIncident();return;}
 incidentPrepared={key:ctx.key,draft};$('incident-draft').value=draft;$('incident-draft').hidden=false;$('incident-copy').disabled=false;$('incident-open-work').hidden=false;$('incident-prepared').textContent='Lokal vorbereitet';$('incident-feedback').textContent='Auftrag vorbereitet, nichts gesendet oder ausgeführt. Vor Übergabe vorhandenen Arbeitschat berücksichtigen.';
});
$('incident-copy').addEventListener('click',async()=>{
 const ctx=activeIncident();
 if(!ctx||!incidentPrepared||ctx.key!==incidentPrepared.key){clearIncident('Befund geändert. Neu vorbereiten.');paintIncident();return;}
 const saved=incidentPrepared;
 try{await navigator.clipboard.writeText(saved.draft);if(incidentPrepared===saved)$('incident-feedback').textContent='Auftrag kopiert. In den vorhandenen Arbeitschat oder Work einfügen. Keine Ausführung ausgelöst.';}
 catch{if(incidentPrepared===saved){$('incident-draft').focus();$('incident-draft').select();$('incident-feedback').textContent='Bitte markierten Text manuell kopieren. Keine Ausführung ausgelöst.';}}
});
$('incident-open-work').addEventListener('click',e=>{
 const ctx=activeIncident();
 if(!ctx||!incidentPrepared||ctx.key!==incidentPrepared.key){e.preventDefault();clearIncident('Befund geändert. Neu vorbereiten.');paintIncident();}
});
