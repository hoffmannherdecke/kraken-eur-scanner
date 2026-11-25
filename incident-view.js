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
 if(issues.some(i=>i?.check==="runtime_supervisor"&&["WARNING","CRITICAL"].includes(i.severity)))codes.push("SUPERVISOR_WARNING");
 if(h?.status==="CRITICAL"||issues.some(i=>i?.severity==="CRITICAL"))codes.push("HOST_CRITICAL");
 else if(h?.status==="WARNING"||issues.some(i=>i?.severity==="WARNING"))codes.push("HOST_WARNING");
 if(!connected||elapsed>75||now-Date.parse(v.read_at)>180000)codes.push("CLOUD_READ_NOT_CURRENT");
 if(!at||m.hostAge===null||m.hostAge>360)codes.push("HOST_REPORT_NOT_CURRENT");
 if(!s)codes.push("ACTIVE_SERIES_UNCONFIRMED");
 if(!codes.length)codes.push("HEALTH_NOT_CONFIRMED");
 const readAt=new Date(Date.parse(v.read_at)).toISOString();
 const current=!!connected&&elapsed<=75&&now-Date.parse(v.read_at)<=180000&&!!at&&m.hostAge!==null&&m.hostAge<=600;
 const key=JSON.stringify([s,at,codes,current,m.tone]);
 return {series:s,hostAt:at,readAt,codes,key,tone:m.tone,current};
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
 clearIncident();$('incident-action').hidden=true;$('incident-create').disabled=true;$('incident-context').textContent='Noch kein bestätigter Cloud-Abruf.';$('incident-detected').textContent='Nicht belegt';
}
function paintIncident(){
 const ctx=activeIncident();
 $('incident-action').hidden=!ctx;
 $('incident-create').disabled=!ctx;
 $('incident-detected').textContent=ctx?'Abweichung / Klärungsbedarf':'Kein Störungsauftrag verfügbar';
 $('incident-context').textContent=ctx?'App-Abruf: '+time(ctx.readAt)+' · Hostbericht: '+time(ctx.hostAt)+' · '+(ctx.current?'Zeitgestempelter Befund':'Aktualität nicht bestätigt'):'Kein aktuell vorbereitbarer Störungsauftrag.';
 if(incidentPrepared&&(!ctx||ctx.key!==incidentPrepared.key))clearIncident('Befund geändert oder nicht mehr verfügbar. Auftrag anhand der neuen Lage vorbereiten.');
}
$('incident-action').addEventListener('click',()=>{
 if(!activeIncident())return;
 document.querySelector('nav button[data-page="system"]').click();
 $('incident-view').scrollIntoView({block:'start',behavior:'auto'});
 $('incident-create').focus({preventScroll:true});
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
