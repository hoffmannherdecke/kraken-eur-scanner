'use strict';
const HOST_REPORT_DUE_SEC=180, HOST_REPORT_STALE_SEC=300, CLOUD_RESPONSE_STALE_SEC=75;
function writerPresentation(h,readAt,current=true){
  const checked=Date.parse(h?.observed_at??"");
  const read=Date.parse(readAt??"");
  const lag=(read-checked)/1000;
  const issue=Array.isArray(h?.issues)?h.issues.find(i=>i?.check==="v3_paper_single_writer"):null;
  const check=issue?{ok:false,detail:issue.detail}:h?.writer&&typeof h.writer.ok==="boolean"?h.writer:null;
  const detail=typeof check?.detail==="string"?check.detail:"";
  const match=detail.match(/(?:^|\s)age_sec=(\d+(?:\.\d+)?)(?:\s|$)/);
  const heartbeatAge=match?Number(match[1]):null;
  const ageText=Number.isFinite(heartbeatAge)?`Heartbeat-Alter beim Bericht: ${Math.round(heartbeatAge/60)} Min. (${Math.round(heartbeatAge)} Sek.).`:"Heartbeat-Alter nicht übermittelt.";
  const last=check?.ok===false?"Letzte Betriebsprüfung fehlgeschlagen.":check?.ok===true?"Letzte Betriebsprüfung bestanden.":"Kein Writer-Prüfergebnis übermittelt.";
  if(!current||!Number.isFinite(lag)||lag< -30||lag>HOST_REPORT_STALE_SEC)return {label:"Writer-Status nicht aktuell",tone:"warn",note:last+" Kein aktueller Laufnachweis.",ageText,detail};
  if(check?.ok===false)return {label:"Writer-Prüfung fehlgeschlagen",tone:"warn",note:"Task, Prozess und Heartbeat konnten beim letzten Hostbericht nicht gemeinsam bestätigt werden. Ursache noch offen.",ageText,detail};
  if(check?.ok===true&&lag>HOST_REPORT_DUE_SEC)return {label:"Writer zuletzt bestätigt – neuer Bericht fällig",tone:"warn",note:"Der letzte Writer-Befund war positiv, ist aber über drei Minuten alt.",ageText,detail};
  if(check?.ok===true)return {label:"Writer beim letzten Hostbericht bestätigt",tone:"good",note:"Die vorhandene lokale Betriebsprüfung war erfolgreich. Dies ist ein zeitgestempelter Nachweis, keine Echtzeitgarantie.",ageText,detail};
  return {label:"Writer-Status nicht belegt",tone:"warn",note:"Noch kein Writer-Prüfergebnis im Cloud-Bericht. Ein aktiver Serieneintrag reicht nicht als Laufnachweis.",ageText,detail};
}
function writerPanel(h,readAt,current=true){
  const v=writerPresentation(h,readAt,current);
  const p=panel(el('h3',v.label,v.tone),el('p',v.note),el('small','Hostbericht: '+time(h?.observed_at)),el('p',v.ageText,'sub'));
  if(v.detail)p.append(detail('Originaler Writer-Prüfbeleg',v.detail));
  return p;
}
