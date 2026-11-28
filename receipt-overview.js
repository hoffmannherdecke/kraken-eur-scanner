'use strict';
function receiptListModel(v,key){
 if(key==="entries"||key==="exits"){const h=paperTradeHistory(v);if(!h)return {available:false,rows:[],total:null,complete:false};const entries=key==="entries";return {available:true,rows:entries?h.entries:h.exits,total:entries?h.entry_window_count:h.exit_window_count,seriesTotal:entries?h.entry_total:h.exit_total,complete:true};}
 const counts={candidates:"candidate_count",journal:"events_count"};
 const active=v?.series?.length===1&&v.series[0].status==="active";
 const total=v?.[counts[key]];
 if(!active||!Number.isSafeInteger(total)||total<0||!Array.isArray(v.decisions))return {available:false,rows:[],total:null,complete:false};
 const end=Date.parse(v.read_at),start=end-v.window_hours*3600000;
 const validWindow=Number.isFinite(end)&&Number.isFinite(start)&&v.window_hours>0;
 if(!validWindow)return {available:false,rows:[],total:null,complete:false};
 const seen=new Set();
 const rows=v.decisions.filter(d=>{
  if(!d||typeof d.candidate_id!=="string"||typeof d.pair!=="string"||typeof d.phase!=="string"||typeof d.result!=="string")return false;
  const t=Date.parse(d.source_known_at);
  if(!Number.isFinite(t)||t<start||t>end)return false;
  if(seen.has(d.candidate_id))return false;
  seen.add(d.candidate_id);return true;
 }).sort((a,b)=>Date.parse(b.source_known_at)-Date.parse(a.source_known_at));
 if(rows.length>total)return {available:false,rows:[],total:null,complete:false};
 return {available:true,rows,total,complete:rows.length===total};
}
const RECEIPT_METRICS=[['candidates','Kandidaten im Zeitraum','candidate_count'],['journal','Journalbelege im Zeitraum','events_count'],['entries','Paper-Einstiegsbelege','fill_count'],['exits','Paper-Abschlussbelege','exit_count']];
function receiptDetailPanel(v,key,current){
 const m=receiptListModel(v,key), label=RECEIPT_METRICS.find(x=>x[0]===key)[1];
 const close=el('button','Zurück zur Übersicht');close.type='button';
 const header=el('div',undefined,'receipt-detail-header');header.append(el('h3',label),close);
 const p=panel(header,el('small',(current?'Cloud-Stand: ':'Letzter erfolgreicher Cloud-Stand (nicht aktuell): ')+time(v.read_at)));
 p.id='receipt-detail-panel';p.setAttribute('role','region');p.setAttribute('aria-label',label);
 close.addEventListener('click',()=>{p.hidden=true;const b=$('summary').querySelector('[data-receipt-key="'+key+'"]');if(b){b.setAttribute('aria-expanded','false');b.focus();}});
 if(!m.available){p.append(el('p','Keine eindeutige Datenbasis für diese Liste.','warn'));return p;}
 p.append(el('p',m.seriesTotal!==undefined?m.total+' Belege · letzte 180 Tage. Seit Serienbeginn: '+m.seriesTotal:m.rows.length+' von '+m.total+' im Cloud-Zeitraum sichtbar.',m.complete?'sub':'warn'));
 if(!m.complete)p.append(el('p','Die Schnittstelle liefert nur den letzten Entscheidungsbeleg von höchstens 30 Kandidaten. Weitere Einzelbelege sind noch nicht verfügbar.','sub'));
 if(key==='journal')p.append(el('small','Die sichtbaren Einträge sind jeweils der letzte übermittelte Entscheidungsbeleg, kein vollständiger Journalexport.'));
 if(!m.rows.length)p.append(el('p',m.total===0?'Keine entsprechenden Cloud-Belege im abgefragten Zeitraum.':'Einzelbelege fehlen in der aktuellen Cloud-Liste.','muted'));
 for(const d of m.rows){
  if(key==='entries'||key==='exits'){
   p.append(paperTradeReceiptCard(d));
  }else p.append(candidate(d));
 }
 return p;
}
function capitalAvailabilityPanel(v,current){
 const p=panel(el('h3','Paper-Kapital & Gesamtperformance'),el('small',(current?'Cloud-Stand: ':'Letzter Cloud-Stand (nicht aktuell): ')+time(v.read_at)),el('p','Gesamtvermögen: nicht verfügbar'),el('p','Frei verfügbares Kapital: nicht verfügbar'),el('p','Investiertes Kapital je Coin: nicht verfügbar'),el('p','Gesamtgewinn / -verlust: nicht bewertbar','warn'),el('small','Die vorhandene Schnittstelle liefert weder einen vollständigen Kapitalbestand noch bestätigte offene Positionen. Keine Schätzung aus Belegzählern.'));
 p.id='capital-availability-panel';return p;
}
const renderBeforeReceiptOverview=render;
render=function(current=true){
 const root=$('summary'),old=root.querySelector('[data-receipt-key][aria-expanded="true"]');
 const previous=old&&root.dataset.receiptSeries===data?.series?.[0]?.series_id?old.dataset.receiptKey:null;
 renderBeforeReceiptOverview(current);
 $('read').textContent='Cloud-Abfrage: '+time(data.read_at)+' · Kandidaten/Journal: '+data.window_hours+' Stunden · Handelsbelege: '+(paperTradeHistory(data)?'letzte 180 Tage':'Historie nicht verfügbar');
 const metrics=root.querySelector('.overview-metrics');if(!metrics)return;
 root.dataset.receiptSeries=data?.series?.length===1?data.series[0].series_id:'';
 const buttons=RECEIPT_METRICS.map(([key,label,field])=>{
  const b=el('button',undefined,'panel receipt-metric-button');b.type='button';b.dataset.receiptKey=key;b.setAttribute('aria-expanded','false');b.setAttribute('aria-controls','receipt-detail-panel');const history=key==='entries'||key==='exits'?receiptListModel(data,key):null;b.append(el('span',history?(history.available?String(history.total):'–'):String(data[field]),'num'),el('small',label+(history?' · 180 Tage':'')+' ›'));if(history)b.append(el('small',history.available?'Seit Serienbeginn: '+history.seriesTotal:'Historie nicht verfügbar'));
  b.addEventListener('click',()=>open(key,true));return b;
 });
 function open(key,manual){
  const currentPanel=$('receipt-detail-panel'),b=buttons.find(x=>x.dataset.receiptKey===key);
  const wasOpen=b.getAttribute('aria-expanded')==='true';
  buttons.forEach(x=>x.setAttribute('aria-expanded','false'));
  if(currentPanel)currentPanel.remove();
  if(manual&&wasOpen)return;
  const p=receiptDetailPanel(data,key,current);metrics.after(p);b.setAttribute('aria-expanded','true');
  if(manual)p.scrollIntoView({block:'start'});
 }
 metrics.replaceChildren(...buttons);metrics.after(capitalAvailabilityPanel(data,current));
 if(previous&&buttons.some(b=>b.dataset.receiptKey===previous))open(previous,false);
};