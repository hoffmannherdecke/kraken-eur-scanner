'use strict';
function sessionRecord(raw,now){
 try{const r=JSON.parse(raw);if(!r||typeof r.key!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(r.key)||!Number.isSafeInteger(r.expires)||r.expires<=now||r.expires>now+8*3600000||!["overview","review","trade","market","learning","system"].includes(r.page))return null;return {key:r.key,expires:r.expires,page:r.page};}catch{return null;}
}
const APP_SESSION_KEY='kraken-eur-scanner:read-session:v1';
let appSession=null,sessionOptIn=false,requestedPage='overview';
function forgetSession(){
 appSession=null;sessionOptIn=false;requestedPage='overview';
 try{sessionStorage.removeItem(APP_SESSION_KEY);}catch{}
}
function loadSession(){
 try{const r=sessionRecord(sessionStorage.getItem(APP_SESSION_KEY),Date.now());if(!r){forgetSession();return null;}return r;}catch{return null;}
}
function saveSession(key,page){
 if(!sessionOptIn)return false;
 const expires=appSession?.expires??Date.now()+8*3600000;
 const r=sessionRecord(JSON.stringify({key,expires,page}),Date.now());
 if(!r){forgetSession();return false;}
 try{sessionStorage.setItem(APP_SESSION_KEY,JSON.stringify(r));appSession=r;return true;}catch{forgetSession();return false;}
}
function rememberPage(page){
 requestedPage=page;
 if(appSession&&sessionOptIn)saveSession(appSession.key,page);
}
function sessionMessage(){
 const p=$('session-info');
 p.textContent=appSession?'Sitzung für Neuladen gespeichert (bis '+new Intl.DateTimeFormat('de-DE',{hour:'2-digit',minute:'2-digit'}).format(new Date(appSession.expires))+').':'Zugang nur im Arbeitsspeicher. Neuladen erfordert Anmeldung.';
}
