'use strict';
function quotePairs(v){
 if(!Array.isArray(v?.series)||v.series.length!==1||v.series[0].status!=="active"||!Array.isArray(v.decisions))return [];
 return [...new Set(["BTC/EUR","ETH/EUR","SOL/EUR",...v.decisions.map(d=>d?.pair).filter(p=>typeof p==="string"&&/^[A-Z0-9]{1,20}\/EUR$/.test(p))])].slice(0,15);
}
function pairCatalog(json){
 if(!Array.isArray(json?.error)||json.error.length||!json.result||Array.isArray(json.result)||typeof json.result!=="object")throw Error("Kraken-Paarliste nicht verfügbar");
 const map=new Map(),amb=new Set();
 for(const [key,p] of Object.entries(json.result)){
 if(!/^[A-Za-z0-9.]{1,40}$/.test(key)||typeof p?.wsname!=="string"||!p.wsname.endsWith("/EUR"))continue;
 const pair=p.wsname==="XBT/EUR"?"BTC/EUR":p.wsname;
 if(!/^[A-Z0-9]{1,20}\/EUR$/.test(pair))continue;
 if(map.has(pair)&&map.get(pair)!==key)amb.add(pair);
 map.set(pair,key);
 }for(const p of amb)map.delete(p);return map;
}
function quoteRows(json,pairs,catalog){
 if(!Array.isArray(json?.error)||json.error.length||!json.result||typeof json.result!=="object"||Array.isArray(json.result))throw Error("Kraken-Kurse nicht verfügbar");
 const n=x=>typeof x==="string"&&x.trim()!==""&&Number.isFinite(Number(x))&&Number(x)>0?Number(x):null;
 return pairs.map(pair=>{
 const key=catalog.get(pair),r=key&&Object.hasOwn(json.result,key)?json.result[key]:null;
 const last=n(r?.c?.[0]),bid=n(r?.b?.[0]),ask=n(r?.a?.[0]),open=n(r?.o);
 if(!last||!bid||!ask||ask<bid)return {pair,available:false};
 return {pair,available:true,last,bid,ask,change:open?(last/open-1)*100:null};
 });
}
function candleRows(json,key,now){
 if(!Array.isArray(json?.error)||json.error.length||!json.result||!Object.hasOwn(json.result,key)||!Array.isArray(json.result[key]))throw Error("Kraken-Kerzen nicht verfügbar");
 const a=json.result[key].slice(0,-1).filter(r=>Array.isArray(r)&&Number.isSafeInteger(r[0])&&r[0]*1000+900000<=now&&r[0]*1000>=now-86400000).map(r=>({t:r[0]*1000,p:typeof r[4]==="string"?Number(r[4]):NaN}));
 if(a.length<2||a.some((r,i)=>!Number.isFinite(r.p)||r.p<=0||i>0&&r.t<=a[i-1].t))throw Error("Kein belastbarer Kursverlauf");
 return a;
}
let quotesGeneration=0,quotesBusy=false,quotesAttempt=0,quotesCatalog=null,quotesCatalogAt=0,quotesSelection='',quotesLast=null,chartGeneration=0,chartBusy=false;
const quotePrice=x=>new Intl.NumberFormat('de-DE',{maximumSignificantDigits:9}).format(x)+' €';
async function krakenPublic(path,params={}){
 const url=new URL('https://api.kraken.com/0/public/'+path);for(const [k,v] of Object.entries(params))url.searchParams.set(k,v);
 const ctrl=new AbortController(),timer=setTimeout(()=>ctrl.abort(),12000);
 try{const r=await fetch(url,{method:'GET',credentials:'omit',referrerPolicy:'no-referrer',cache:'no-store',signal:ctrl.signal});if(!r.ok)throw Error('Kraken nicht erreichbar');return await r.json();}finally{clearTimeout(timer);}
}
function resetQuotes(){
 quotesGeneration++;chartGeneration++;quotesBusy=false;chartBusy=false;quotesAttempt=0;quotesSelection='';quotesLast=null;
 $('quote-note').textContent='Abruf bei sichtbarer Marktansicht.';$('quote-list').replaceChildren();$('quote-chart').replaceChildren();$('quote-pair').replaceChildren();$('quote-chart-btn').disabled=true;
}
function quoteVisible(){return !!data&&!document.hidden&&!$('market').hidden;}
function quoteRender(rows,at,stale=false){
 const items=rows.map(r=>{
 const p=panel(el('h3',r.pair));
 if(!r.available){p.append(el('p','Kurs nicht verfügbar','warn'));return p;}
 p.append(el('p',quotePrice(r.last),'quote-number'),el('p','Geld '+quotePrice(r.bid)+' · Brief '+quotePrice(r.ask),'sub'));
 if(r.change!==null)p.append(el('small',(r.change>=0?'+':'')+r.change.toFixed(2).replace('.',',')+' % seit 00:00 UTC'));
 return p;});
 put('quote-list',...items);
 $('quote-note').textContent=(stale?'Letzter erfolgreicher Abruf – nicht aktuell: ':'Kraken-Abruf: ')+time(at)+' · Zeitpunkt des letzten einzelnen Handels nicht belegt.';
}
async function refreshQuotes(force=false){
 if(!quoteVisible()||quotesBusy)return;
 const pairs=quotePairs(data),selection=pairs.join(',');
 if(!pairs.length){resetQuotes();return;}
 if(!force&&selection===quotesSelection&&Date.now()-quotesAttempt<60000)return;
 const g=quotesGeneration;quotesBusy=true;quotesAttempt=Date.now();
 if(selection!==quotesSelection){chartGeneration++;chartBusy=false;quotesLast=null;put('quote-list');put('quote-chart');$('quote-pair').replaceChildren();$('quote-chart-btn').disabled=true;quotesSelection=selection;}
 $('quote-note').textContent='Öffentliche Kraken-Kurse werden abgerufen …';
 try{
 if(!quotesCatalog||Date.now()-quotesCatalogAt>3600000){const cat=pairCatalog(await krakenPublic('AssetPairs'));if(g!==quotesGeneration)return;quotesCatalog=cat;quotesCatalogAt=Date.now();}
 const keys=pairs.map(p=>quotesCatalog.get(p)).filter(Boolean);
 if(!keys.length)throw Error('Keine eindeutigen EUR-Paare');
 const rows=quoteRows(await krakenPublic('Ticker',{pair:keys.join(',')}),pairs,quotesCatalog);
 if(g!==quotesGeneration)return;
 if(quotePairs(data).join(',')!==selection){quotesAttempt=0;return;}
 const at=new Date().toISOString();quotesLast={rows,at};quoteRender(rows,at);
 const old=$('quote-pair').value;$('quote-pair').replaceChildren();for(const p of pairs.filter(p=>quotesCatalog.has(p))){const o=el('option',p);o.value=p;$('quote-pair').append(o);}if([...$('quote-pair').options].some(o=>o.value===old))$('quote-pair').value=old;$('quote-chart-btn').disabled=!$('quote-pair').value;
 }catch{if(g!==quotesGeneration)return;if(quotesLast)quoteRender(quotesLast.rows,quotesLast.at,true);else{$('quote-note').textContent='Kraken-Abruf fehlgeschlagen (Netz, Browser oder API). Keine Ersatzkurse.';put('quote-list');}}finally{if(g===quotesGeneration)quotesBusy=false;}
}
function showQuoteChart(pair,rows){
 const lo=Math.min(...rows.map(r=>r.p)),hi=Math.max(...rows.map(r=>r.p)),span=hi-lo||lo*0.01,start=rows[0].t,end=rows.at(-1).t;
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 320 116');svg.setAttribute('role','img');svg.setAttribute('aria-label',pair+' Schlusskurse der abgeschlossenen 15-Minuten-Intervalle');svg.classList.add('quote-chart-svg');
 const x=r=>10+300*(r.t-start)/(end-start),y=r=>106-96*(r.p-lo)/span;let segment=[];
 const flush=()=>{if(segment.length){const path=document.createElementNS(svg.namespaceURI,'polyline');path.setAttribute('points',segment.map(r=>x(r)+','+y(r)).join(' '));path.setAttribute('fill','none');path.setAttribute('stroke','currentColor');path.setAttribute('stroke-width','2');svg.append(path);segment=[];}};
 for(let i=0;i<rows.length;i++){if(i&&rows[i].t-rows[i-1].t!==900000)flush();segment.push(rows[i]);}flush();
 const p=panel(el('h3',pair+' · bis zu 24 Stunden'),svg,el('p','Minimum '+quotePrice(lo)+' · Maximum '+quotePrice(hi),'sub'),el('small','Erste bis letzte abgeschlossene 15-Minuten-Kerze: '+time(new Date(start+900000).toISOString())+' – '+time(new Date(end+900000).toISOString())),el('p','Kursverlauf beim Abruf. Lücken werden nicht verbunden. Keine historischen Einstiegspreise aus diesen Kursen ableiten.','sub'));
 const events=(data?.decisions||[]).filter(d=>d.pair===pair);if(events.length){p.append(el('h3','Letzte belegte Entscheidungen (separat)'));for(const d of events)p.append(el('p',time(d.source_known_at)+' · '+(statuses[d.result]?.[0]||d.result),'sub'));}
 put('quote-chart',p);
}
async function loadQuoteChart(){
 if(!quoteVisible()||chartBusy||!quotesCatalog)return;
 const pair=$('quote-pair').value,key=quotesCatalog.get(pair);if(!key)return;
 const g=++chartGeneration;chartBusy=true;put('quote-chart',panel(el('p','Kursverlauf wird geladen …')));
 try{const json=await krakenPublic('OHLC',{pair:key,interval:'15',since:String(Math.floor(Date.now()/1000)-86400)});if(g!==chartGeneration)return;showQuoteChart(pair,candleRows(json,key,Date.now()));}catch{if(g===chartGeneration)put('quote-chart',panel(el('p','Kein gültiger Kursverlauf verfügbar.','warn')));}finally{if(g===chartGeneration)chartBusy=false;}
}
$('quote-chart-btn').addEventListener('click',loadQuoteChart);
$('quote-pair').addEventListener('change',()=>{chartGeneration++;chartBusy=false;put('quote-chart');});
