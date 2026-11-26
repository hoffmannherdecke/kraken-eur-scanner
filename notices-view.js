'use strict';
function noticeOriginalId(url){const m=typeof url==="string"&&url.match(/^https:\/\/github\.com\/hoffmannherdecke\/kraken-eur-scanner\/issues\/99#issuecomment-(\d+)$/);return m?m[1]:null;}
function parseNoticeOwner(issue){
 if(issue?.number!==99||typeof issue.body!=="string")return null;
 const matches=[...issue.body.matchAll(/<!-- CURRENT_PAPER_OPERATIONAL_STATUS_V1\s*\n([\s\S]*?)\nEND_CURRENT_PAPER_OPERATIONAL_STATUS_V1 -->/g)];
 if(matches.length!==1)return null;
 try{const r=JSON.parse(matches[0][1]);const expected=["series_id","strategy_revision","strategy_version","source","observed_at_utc","lease_expires_at_utc","lease_source","review_requests"];
 if(Object.keys(r).length!==expected.length||!expected.every(k=>Object.hasOwn(r,k))||typeof r.series_id!=="string"||typeof r.strategy_revision!=="string"||!/^V\d+$/.test(r.strategy_version)||!noticeOriginalId(r.source)||!noticeOriginalId(r.lease_source)||!Number.isFinite(Date.parse(r.observed_at_utc))||(r.lease_expires_at_utc!==null&&(!Number.isFinite(Date.parse(r.lease_expires_at_utc))||Date.parse(r.lease_expires_at_utc)<=Date.parse(r.observed_at_utc))))return null;return r;}catch{return null;}
}
function verifyNoticeProof(record,release,lease){
 if(!record)return false;
 const match=(o,url)=>o&&String(o.id)===noticeOriginalId(url)&&o.html_url===url&&typeof o.body==="string"&&o.body.includes(record.series_id);
 if(!match(release,record.source)||!match(lease,record.lease_source)||!release.body.includes(record.strategy_version+"_PAPER_OPERATIONAL"))return false;
 if(record.lease_expires_at_utc===null)return /\bV3_PAPER_RUNTIME_UNTIL_REVOKED\b/.test(lease.body);
 const iso=new Date(record.lease_expires_at_utc).toISOString(),ymd=iso.slice(0,10),dmy=ymd.split("-").reverse().join("."),clock=iso.slice(11,19);
 return /lease/i.test(lease.body)&&lease.body.includes(clock)&&(lease.body.includes(ymd)||lease.body.includes(dmy));
}
function noticeModel(snapshot,record,verified,current=true){
 if(!current||!verified||!record||!Array.isArray(snapshot?.series)||snapshot.series.length!==1||snapshot.series[0].status!=="active"||snapshot.series[0].series_id!==record.series_id)return {state:"unknown"};
 const now=Date.parse(snapshot.read_at),observed=Date.parse(record.observed_at_utc);
 if(!Number.isFinite(now)||!Number.isFinite(observed)||observed>now)return {state:"unknown"};
 if(record.lease_expires_at_utc===null)return {state:"unbounded",source:record.lease_source};
 const expiry=Date.parse(record.lease_expires_at_utc);
 if(!Number.isFinite(expiry))return {state:"unknown"};
 const remaining=expiry-now;return {state:remaining<=0?"expired":remaining<=72*3600000?"review_due":"not_due",expiry:record.lease_expires_at_utc,source:record.lease_source,remainingHours:Math.max(0,Math.ceil(remaining/3600000))};
}
const NOTICE_API='https://api.github.com/repos/hoffmannherdecke/kraken-eur-scanner';
const NOTICE_MAX_AGE=15*60*1000;
let noticeRecord=null,noticeChecked=0,noticeBusy=false,noticeGeneration=0,noticeSeries=null,noticeCloudCurrent=false;
function noticeLink(url){const a=el('a','Originalnachweis öffnen','blue');a.href=url;a.target='_blank';a.rel='noopener noreferrer';return a;}
function renderNotices(v,current=true){
 noticeCloudCurrent=current;const age=Date.now()-noticeChecked;
 const m=noticeModel(v,noticeRecord,!!noticeRecord&&age>=0&&age<=NOTICE_MAX_AGE,current);
 put('action-notices');const p=panel(el('h3','Betriebsberechtigung & Hinweise'));
 if(m.state==='unknown')p.append(el('p','Aktuelle Frist nicht eindeutig bestätigt.','warn'),el('small','Kein verifizierter seriengebundener Abruf. Keine automatische Freigabe.'));
 else if(m.state==='unbounded'){
  p.append(el('p','Zuletzt belegte Freigabe: unbefristeter Paper-Betrieb bis zum Widerruf'),el('small','Der aktuelle Writer-Zustand steht unter Systemzustand.'),noticeLink(m.source));
 }else{
  p.append(el('p','Zuletzt belegte Laufzeitfreigabe bis '+time(m.expiry)),el('small','Originalreferenz geprüft; keine eigenständige Prüfung der aktiven CMS-Berechtigung.'),noticeLink(m.source));
  if(m.state==='not_due')p.append(el('p','Der bestehende 72-Stunden-Vorbereitungshinweis ist noch nicht fällig.','muted'));
  else{
   const expired=m.state==='expired',title=expired?'Zuletzt belegte Betriebsfrist abgelaufen':'Verlängerung rechtzeitig vorbereiten';
   const msg=expired?'Aktuellen Originalhost und die gültige Freigabe beim zuständigen Betriebsowner prüfen. Kein automatischer Neustart.':'Die zuletzt belegte Frist endet in höchstens 72 Stunden. Der bestehende Projektprozess muss die persönliche Verlängerungsfreigabe rechtzeitig vorbereiten. Dies ist noch keine Aufforderung zur Signatur.';
   const n=panel(el('h3',title,'warn'),el('p',msg),el('small','Frist: '+time(m.expiry)),noticeLink(m.source));n.classList.add('action-notice');put('action-notices',n);p.append(el('p',title,'warn'));
  }
 }
 p.append(el('p','Aktive Push-Meldungen bleiben beim vorhandenen Slack-/iPhone-Meldeweg. Diese App sendet keine zusätzlichen Push-Nachrichten.','sub'),el('small','Normale Kandidatenmeldungen und gewöhnliche Warnungen lösen keine neue Benachrichtigung aus.'));put('notice-system',p);
}
function resetNotices(){noticeGeneration++;noticeRecord=null;noticeChecked=0;noticeBusy=false;noticeSeries=null;noticeCloudCurrent=false;put('action-notices');put('notice-system');}
async function noticeJSON(path){const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);try{const r=await fetch(NOTICE_API+path,{credentials:'omit',referrerPolicy:'no-referrer',cache:'no-cache',signal:controller.signal});if(!r.ok)throw Error('Original nicht erreichbar');return r.json();}finally{clearTimeout(timer);}}
async function refreshNoticeOwner(){
 const sid=data?.series?.length===1?data.series[0].series_id:null;if(!sid||noticeBusy)return;
 const age=Date.now()-noticeChecked;if(noticeSeries===sid&&age>=0&&age<NOTICE_MAX_AGE)return;
 noticeBusy=true;const generation=noticeGeneration;
 try{const r=parseNoticeOwner(await noticeJSON('/issues/99'));if(!r||r.series_id!==sid)throw Error('Serie nicht zugeordnet');const release=await noticeJSON('/issues/comments/'+noticeOriginalId(r.source));const lease=r.lease_source===r.source?release:await noticeJSON('/issues/comments/'+noticeOriginalId(r.lease_source));if(!verifyNoticeProof(r,release,lease))throw Error('Original nicht bestätigt');if(generation!==noticeGeneration)return;noticeRecord=r;}
 catch{if(generation!==noticeGeneration)return;noticeRecord=null;}
 finally{if(generation===noticeGeneration){noticeChecked=Date.now();noticeSeries=sid;noticeBusy=false;if(data)renderNotices(data,noticeCloudCurrent);}}
}
