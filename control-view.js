'use strict';
function controlContext(v,current=true,now=Date.now()){
 if(!current||!Array.isArray(v?.series)||v.series.length!==1||v.series[0].status!=="active"||typeof v.series[0].series_id!=="string"||!/^PAPER-V3-\d{8}T\d{6}Z$/.test(v.series[0].series_id))return null;
 const t=Date.parse(v.read_at);
 if(!Number.isFinite(t)||!Number.isFinite(now)||now-t>180000||t-now>30000)return null;
 return {series:v.series[0].series_id,readAt:v.read_at};
}
function controlDraft(action,ctx){
 if(!ctx)return null;
 const requests={
 pause:["Neue Einstiege pausieren","Prüfe eine gezielte Pause neuer Paper-Einstiege. Offene Positionen, WAIT-Bestandsfälle, erforderliche Nachbetrachtungen und Cloud-Synchronisierung dürfen nicht unbeaufsichtigt bleiben. Nur bei nachgewiesener geeigneter vorhandener Schnittstelle und nach erforderlicher Freigabe ausführen; andernfalls kleinsten fehlenden Vertrag benennen."],
 stop:["Kontrollierten Betriebsstopp vorbereiten","Prüfe einen kontrollierten HOLD des aktiven Paper-Writers einschließlich tatsächlichem Positionsbestand, gesicherter Nachbetreuung, offenen Journal-/Cloud-ACKs und unverändertem Fence. Keine Wiederverwendung des alten V2R4-STOP. STOP nur nach aktueller konkreter Ownerfreigabe, anschließend unabhängiger Host-/Cloud-Nachweis."],
 resume:["Betriebswiederaufnahme vorbereiten","Prüfe die zulässige Wiederaufnahme derselben aktiven Paper-Serie anhand aktueller Host-/Cloud-Originale, Ursache eines etwaigen HOLD, Writer-Identität, gültiger Lease und vorhandener Freigabegrenzen. PaperResume ist nur lesend. Kein Blind-Restart, keine alte Aktivierungskennung, kein erneuter CAS und keine Wiederaufnahme des Vorgängers."],
 settings:["Betriebseinstellungen prüfen","Prüfe die von mir noch zu benennende konkrete Betriebseinstellung anhand des aktuellen Originalvertrags. Keine Änderung der laufenden Strategie, der Kosten, der Rechte oder der Runtime ohne jeweils notwendige Freigabe und passenden Nachweis."]
 };
 if(!Object.hasOwn(requests,action))return null;
 const [title,body]=requests[action];
 return "KRYPTO – Prüfauftrag: "+title+"\n\nAktive Cloud-Serie laut App-Abruf: "+ctx.series+"\nZeitpunkt des App-Abrufs (UTC): "+ctx.readAt+"\n\n"+body+"\n\nBestehenden zuständigen Arbeitsauftrag und #99/#353 berücksichtigen; keine parallele Ausführung. App-Information ist kein Originalhost-Nachweis. Dieser Entwurf ist weder eine Ausführungsfreigabe noch ein Steuerungsbefehl. Kein Echtgeld.";
}
let controlCurrent=false,controlDraftSeries=null,controlDraftAction=null,controlDraftText=null;
function clearControlDraft(message='Noch kein Entwurf erstellt.'){
 controlDraftSeries=null;controlDraftAction=null;controlDraftText=null;
 $('control-draft').value='';$('control-draft').hidden=true;$('control-copy').disabled=true;
 $('control-feedback').textContent=message;
}
function renderControl(v,current=true){
 controlCurrent=current;
 const ctx=controlContext(v,current);
 $('control-create').disabled=!ctx;
 $('control-context').textContent=ctx?'Cloud-Serie: '+ctx.series+' · Abruf: '+time(ctx.readAt):'Keine eindeutig aktuelle V3-Cloud-Serie. Entwurf vorerst nicht verfügbar.';
 if(!ctx||controlDraftSeries&&controlDraftSeries!==ctx.series)clearControlDraft('Bitte nach aktuellem Datenabruf neu vorbereiten.');
}
function resetControl(){
 controlCurrent=false;$('control-action').value='pause';$('control-create').disabled=true;
 $('control-context').textContent='Noch kein bestätigter Cloud-Abruf.';clearControlDraft();
}
$('control-action').addEventListener('change',()=>clearControlDraft());
$('control-create').addEventListener('click',()=>{
 const ctx=controlContext(data,controlCurrent),action=$('control-action').value;
 const text=controlDraft(action,ctx);
 if(!text){clearControlDraft('Aktuelle Daten oder zulässige Auswahl fehlen.');return;}
 controlDraftSeries=ctx.series;controlDraftAction=action;controlDraftText=text;
 $('control-draft').value=text;$('control-draft').hidden=false;$('control-copy').disabled=false;
 $('control-feedback').textContent='Nur lokal vorbereiteter Text. Nichts gesendet oder ausgeführt.';
});
$('control-copy').addEventListener('click',async()=>{
 const ctx=controlContext(data,controlCurrent);
 if(!ctx||ctx.series!==controlDraftSeries||$('control-action').value!==controlDraftAction||!controlDraftText){clearControlDraft('Bitte mit aktuellem Abruf neu vorbereiten.');return;}
 const text=controlDraft(controlDraftAction,ctx);
 $('control-draft').value=text;
 try{await navigator.clipboard.writeText(text);if(controlDraftSeries===ctx.series)$('control-feedback').textContent='Entwurf kopiert. Nichts gesendet. Du kannst ihn im zuständigen Arbeitschat verwenden.';}
 catch{$('control-draft').focus();$('control-draft').select();$('control-feedback').textContent='Automatisches Kopieren nicht verfügbar. Bitte markierten Text manuell kopieren.';}
});
