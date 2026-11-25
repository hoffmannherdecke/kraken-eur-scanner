'use strict';
function sessionRecord(raw,now){
 try{const r=JSON.parse(raw);if(!r||typeof r.key!=="string"||!/^[A-Za-z0-9_-]{43}$/.test(r.key)||!Number.isSafeInteger(r.expires)||r.expires<=now||r.expires>now+8*3600000||!["overview","review","trade","market","learning","system"].includes(r.page))return null;return {key:r.key,expires:r.expires,page:r.page};}catch{return null;}
}
const APP_SESSION_KEY='kraken-eur-scanner:read-session:v1';
const DEVICE_SESSION_KEY='kraken-eur-scanner:device-read-session:v1';
let appSession=null,sessionOptIn=false,deviceOptIn=false,requestedPage='overview';
function sessionStorageFor(device){return device?window.localStorage:window.sessionStorage;}
function removeSession(device){try{sessionStorageFor(device).removeItem(device?DEVICE_SESSION_KEY:APP_SESSION_KEY);return true;}catch{return false;}}
function forgetSession(){
 appSession=null;sessionOptIn=false;deviceOptIn=false;requestedPage='overview';
 const a=removeSession(false),b=removeSession(true);return a&&b;
}
function readSavedSession(device){
 try{const store=sessionStorageFor(device),id=device?DEVICE_SESSION_KEY:APP_SESSION_KEY,raw=store.getItem(id);if(raw===null)return null;const r=sessionRecord(raw,Date.now());if(!r)store.removeItem(id);return r;}catch{return null;}
}
function loadSession(){
 const device=readSavedSession(true);if(device)return {...device,device:true};
 const legacy=readSavedSession(false);return legacy?{...legacy,device:false}:null;
}
function saveSession(key,page){
 if(!sessionOptIn)return false;
 const expires=appSession?.expires??Date.now()+8*3600000;
 const r=sessionRecord(JSON.stringify({key,expires,page}),Date.now());
 if(!r){forgetSession();return false;}
 try{const store=sessionStorageFor(deviceOptIn),id=deviceOptIn?DEVICE_SESSION_KEY:APP_SESSION_KEY,value=JSON.stringify(r);
 if(store.getItem(id)!==value)store.setItem(id,value);
 appSession=r;return true;
 }catch{if(deviceOptIn){removeSession(true);deviceOptIn=false;return saveSession(key,page);}sessionOptIn=false;appSession=null;removeSession(false);return false;}
}
function rememberPage(page){
 requestedPage=page;
 if(appSession&&sessionOptIn)saveSession(appSession.key,page);
}
function sessionMessage(){
 const p=$('session-info'),saved=appSession;
 p.textContent=saved?(deviceOptIn?'Auf diesem Gerät angemeldet bis ':'Sitzung für Neuladen gespeichert bis ')+new Intl.DateTimeFormat('de-DE',{hour:'2-digit',minute:'2-digit'}).format(new Date(saved.expires))+(deviceOptIn?' (auch nach Schließen).':'.'):'Zugang nur im Arbeitsspeicher. Neuladen erfordert Anmeldung.';
 $('device-remember-wrap').hidden=!data||$('login').hidden!==true||deviceOptIn;
}
function enableDeviceSession(){
 if(!access||!data||!healthConnected||healthReceiptMs===null||Date.now()-healthReceiptMs>75000||$('login').hidden!==true||appSession&&appSession.expires<=Date.now())return;
 sessionOptIn=true;deviceOptIn=true;saveSession(access,requestedPage);
 if(deviceOptIn&&appSession)removeSession(false);
 sessionMessage();
 if(!deviceOptIn)$('session-info').textContent+=' Gerätespeicherung nicht verfügbar.';
}
function appReloadURL(href,stamp){
 const u=new URL('./',href);u.searchParams.set('app_reload',String(stamp));return u.href;
}
$('app-reload').addEventListener('click',()=>{
 if(appSession&&appSession.expires<=Date.now())lock();
 location.replace(appReloadURL(location.href,Date.now()));
});
$('device-remember').addEventListener('click',enableDeviceSession);
window.addEventListener('storage',e=>{
 if(!deviceOptIn||!appSession||!(e.key===DEVICE_SESSION_KEY||e.key===null))return;
 const r=readSavedSession(true);
 if(!r||r.key!==appSession.key||r.expires!==appSession.expires){
  appSession=null;sessionOptIn=false;deviceOptIn=false;requestedPage='overview';removeSession(false);lock(false);
 }
});
