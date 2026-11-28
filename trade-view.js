'use strict';
function paperTradeHistory(v){
 const h=v?.paper_trade_receipts,n=x=>Number.isSafeInteger(x)&&x>=0,t=Date.parse(v?.read_at);
 if(!h||h.kind!=="PAPER_TRADE_RECEIPTS_V1"||h.window_days!==180||h.read_at!==v.read_at||v.series?.length!==1||v.series[0].status!=="active"||h.series_id!==v.series[0].series_id||!Number.isFinite(t)||Date.parse(h.window_start)!==t-180*86400000||![h.entry_total,h.exit_total,h.entry_window_count,h.exit_window_count].every(n)||h.entry_window_count>h.entry_total||h.exit_window_count>h.exit_total||!Array.isArray(h.rows)||h.rows.length!==h.entry_window_count+h.exit_window_count||h.rows.length>5000)return null;
 const ids=new Set(),entries=[],exits=[];
 for(const d of h.rows){
  const k=Date.parse(d?.source_known_at),r=Date.parse(d?.received_at);
  if(typeof d?.event_id!=="string"||!d.event_id||ids.has(d.event_id)||typeof d.candidate_id!=="string"||!d.candidate_id||typeof d.pair!=="string"||!Number.isFinite(k)||!Number.isFinite(r)||k<t-180*86400000||k>t||r>t)return null;
  if(d.phase==="PAPER_FILL"&&d.result==="PAPER_FILLED")entries.push(d);else if(d.phase==="PAPER_EXIT"&&d.result==="CLOSED")exits.push(d);else return null;
  ids.add(d.event_id);
 }
 if(entries.length!==h.entry_window_count||exits.length!==h.exit_window_count)return null;
 return {...h,entries,exits};
}
function paperTradeLabel(v){const h=paperTradeHistory(v);return h?"Letzte 180 Tage: "+h.entry_window_count+" Einstiege · "+h.exit_window_count+" Abschlüsse. Seit Beginn der aktiven Serie: "+h.entry_total+" Einstiege · "+h.exit_total+" Abschlüsse.":"Historische Handelsbelege nicht verfügbar; keine Null-Aussage.";}
function tradeViewModel(v,current=true){
 const h=paperTradeHistory(v);
 if(!h)return {available:false};
 return {available:true,current,fillCount:h.entry_window_count,exitCount:h.exit_window_count,entryTotal:h.entry_total,exitTotal:h.exit_total,events:h.rows,readAt:h.read_at,series:h.series_id,windowStart:h.window_start};
}
function renderTrade(v,current=true){
 const m=tradeViewModel(v,current);
 if(!m.available){put('trade-info',panel(el('h3','Historische Handelsbelege nicht verfügbar','warn'),el('p','Keine vollständige Datenbasis für 180 Tage und Seriengesamtzahlen. Keine Null-Aussage.')),...economicPanels(v,current),...opportunityPanels(v,current));return;}
 const metrics=el('div',undefined,'metrics');
 metrics.append(metric(m.fillCount,'Paper-Einstiege · 180 Tage'),metric(m.exitCount,'Paper-Abschlüsse · 180 Tage'),metric(m.entryTotal,'Einstiege seit Serienbeginn'),metric(m.exitTotal,'Abschlüsse seit Serienbeginn'));
 const cards=[panel(el('h3',m.current?'Handelsbelege der aktiven Serie':'Letzter erfolgreicher Abruf',m.current?'blue':'warn'),el('p','Zeitraum: letzte 180 Tage · '+time(m.windowStart)+' bis '+time(m.readAt)),el('small','Serie: '+m.series),el('small','Alle Werte betreffen simulierten Handel.')),metrics,panel(el('h3','Offene Positionen: nicht belegt','warn'),el('p','Handelsereignisse sind kein vollständiger Positionsbestand.')),panel(el('h3','Nettoergebnis nicht separat ausgewiesen','muted'),el('p','Die Belegzahlen sind keine Nettoauswertung.'))];
 cards.push(el('h2','Handelsereignisse · letzte 180 Tage'));
 if(m.events.length)cards.push(...m.events.map(d=>panel(candidate(d),el('small','Original-Ereignis: '+d.event_id))));else cards.push(panel(el('p','Keine entsprechenden Cloud-Belege in den letzten 180 Tagen.','muted')));
 cards.push(panel(el('small','Eigenständige Handelsereignisse der aktiven Serie; nicht auf 30 Kandidaten begrenzt. Noch nicht synchronisierte Vorgänge fehlen.')));
 put('trade-info',...cards,...economicPanels(v,current),...opportunityPanels(v,current));
}

function economicViewModel(v,current=true){
 const l=v?.economic_ledger,invalid=()=>null,n=x=>Number.isSafeInteger(x)&&x>=0,num=x=>typeof x==="number"&&Number.isFinite(x);
 if(!l||l.kind!=="KRYPTO_ECONOMIC_LEDGER_V1"||l.status!=="COMPLETE_CLOUD_RECEIPTS_ONLY"||v.series?.length!==1||v.series[0]?.status!=="active"||l.series_id!==v.series[0].series_id||l.read_at!==v.read_at||!Number.isFinite(Date.parse(v.read_at))||l.real_money!==false||l.live_positions_verified!==false||!n(l.receipt_count)||l.receipt_count>5000)return invalid();
 const s=l.stats,hs=l.horizons,cs=l.candidates,keys=["candidate_count","entry_count","entry_without_exit_count","exit_count","unclear_candidates","closed_with_net_count"],dec=["WAIT","REJECT","BUY_SCOUT","UNKNOWN"],cats=["no_buy_mature","estimated_paper_mature","censored","not_due","missing_or_unresolved","conflict"];
 if(!s||!keys.every(k=>n(s[k]))||!s.initial||!dec.every(k=>n(s.initial[k]))||dec.reduce((a,k)=>a+s.initial[k],0)!==s.candidate_count||s.candidate_count>l.receipt_count||s.entry_without_exit_count+s.exit_count!==s.entry_count||s.entry_count+s.unclear_candidates>s.candidate_count||s.closed_with_net_count>s.exit_count)return invalid();
 if(s.net_eur!==null&&(!num(s.net_eur)||!s.exit_count||s.unclear_candidates||s.closed_with_net_count!==s.exit_count))return invalid();
 if(!Array.isArray(hs)||hs.length!==3||!hs.every((h,i)=>h?.hours===[6,24,72][i]&&cats.every(k=>n(h[k]))&&cats.reduce((a,k)=>a+h[k],0)===s.candidate_count))return invalid();
 if(l.candidate_list_limit!==30||!Array.isArray(cs)||cs.length!==Math.min(30,s.candidate_count)||new Set(cs.map(c=>c?.candidate_id)).size!==cs.length)return invalid();
 for(const c of cs){
 if(typeof c?.candidate_id!=="string"||typeof c.pair!=="string"||!c.pair.endsWith("/EUR")||!dec.includes(c.initial_decision)||!["UNCLEAR","EXIT_RECORDED","ENTRY_WITHOUT_EXIT_RECEIPT","NO_ENTRY_RECEIPT"].includes(c.status)||!Array.isArray(c.followups)||c.followups.length!==3)return invalid();
 if(!["entry_ask_eur","entry_qty","entry_fee_eur","exit_bid_eur","exit_net_eur"].every(k=>c[k]===null||num(c[k])))return invalid();
 const hasEntry=["EXIT_RECORDED","ENTRY_WITHOUT_EXIT_RECEIPT"].includes(c.status),hasExit=c.status==="EXIT_RECORDED";
 if(hasEntry?(!Number.isFinite(Date.parse(c.entry_at))||!num(c.entry_ask_eur)||c.entry_ask_eur<=0||!num(c.entry_qty)||c.entry_qty<=0||!num(c.entry_fee_eur)||c.entry_fee_eur<0):c.entry_at!==null||c.entry_ask_eur!==null||c.entry_qty!==null||c.entry_fee_eur!==null)return invalid();
 if(hasExit?(!Number.isFinite(Date.parse(c.exit_at))||Date.parse(c.exit_at)<Date.parse(c.entry_at)):c.exit_at!==null||c.exit_bid_eur!==null||c.exit_net_eur!==null)return invalid();
 for(let i=0;i<3;i++){const h=c.followups[i];if(!h||h.hours!==[6,24,72][i]||!cats.includes(h.status))return invalid();
 if(h.status==="no_buy_mature"&&(hasEntry||c.status==="UNCLEAR"||![h.mfe_pct,h.mae_pct,h.close_return_pct].every(num)||h.estimated_net_eur!=null||h.estimated_return_pct!=null))return invalid();
 if(h.status==="estimated_paper_mature"&&(!hasEntry||![h.estimated_net_eur,h.estimated_return_pct].every(num)))return invalid();
 if(!["no_buy_mature","estimated_paper_mature"].includes(h.status)&&[h.estimated_net_eur,h.estimated_return_pct,h.mfe_pct,h.mae_pct,h.close_return_pct].some(x=>x!=null))return invalid();}
 }
 return {current,ledger:l};
}
function economicPanels(v,current=true){
 const m=economicViewModel(v,current);
 if(!m)return [panel(el('h3','Wirtschaftsauswertung der gesamten Serie','warn'),el('p','Der vorhandene Cloud-Zugang liefert noch keinen bestätigten vollständigen Serienexport. Die historischen Handelsbelege werden getrennt oben ausgewiesen.'))];
 const l=m.ledger,s=l.stats,eur=x=>typeof x==='number'?new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR',maximumFractionDigits:6}).format(x):'Nicht belegt',pct=x=>typeof x==='number'?new Intl.NumberFormat('de-DE',{maximumFractionDigits:3}).format(x)+' %':'Nicht belegt';
 const cards=[panel(el('h3',m.current?'Wirtschaftliche Belege der gesamten aktiven Serie':'Letzter erfolgreicher Wirtschaftsdatenabruf',m.current?'blue':'warn'),el('small','Stand: '+time(l.read_at)),el('p',l.receipt_count+' Cloud-Journalbelege · '+s.candidate_count+' Kandidaten'),el('p','Erstentscheidungen: '+s.initial.WAIT+' WAIT · '+s.initial.REJECT+' REJECT · '+s.initial.BUY_SCOUT+' BUY · '+s.initial.UNKNOWN+' unklar'),el('small','Nicht synchronisierte lokale Belege fehlen.')),panel(el('h3','Virtuelle Handelsbelege'),el('p','Einstiege: '+s.entry_count+' · Abschlüsse: '+s.exit_count),el('p','Einstiegsbelege ohne Abschlussbeleg: '+s.entry_without_exit_count),el('p','Aktuell offene Positionen: nicht nachgewiesen','warn'),el('p','Belegtes Netto aus Abschlüssen: '+eur(s.net_eur)),el('small','Unklare Kandidaten: '+s.unclear_candidates+'. Keine realen Börsenausführungen.'))];
 for(const h of l.horizons)cards.push(panel(el('h3',h.hours+'-Stunden-Nachbetrachtung'),el('p','Gereifte virtuelle Schätzungen: '+h.estimated_paper_mature+' · Kursbeobachtungen ohne Einstieg: '+h.no_buy_mature),el('p','Noch nicht fällig: '+h.not_due+' · fehlend/ungeklärt: '+h.missing_or_unresolved+' · Datenlücken: '+h.censored+' · widersprüchlich: '+h.conflict),el('small','Keine Addition verschiedener Zeitfenster zu einem Gewinn.')));
 const list=el('details');list.append(el('summary','Einzelne Kandidaten (maximal 30)'));
 for(const c of l.candidates){const box=panel(el('h3',c.pair),el('small','Erstentscheidung: '+c.initial_decision));if(c.entry_at)box.append(el('p','Virtueller Einstieg: '+eur(c.entry_ask_eur)+' · Menge '+c.entry_qty+' · Gebühr '+eur(c.entry_fee_eur)));if(c.exit_at)box.append(el('p','Abschlussbeleg: '+eur(c.exit_net_eur)));for(const h of c.followups){let label={no_buy_mature:'Kursentwicklung ohne Einstieg',estimated_paper_mature:'Geschätztes Paper-Netto',not_due:'Noch nicht fällig',censored:'Datenlücke',conflict:'Widersprüchlich',missing_or_unresolved:'Fehlend oder ungeklärt'}[h.status];if(h.status==='no_buy_mature')label+=' · Hoch '+pct(h.mfe_pct)+' · Tief '+pct(h.mae_pct)+' · Ende '+pct(h.close_return_pct);if(h.status==='estimated_paper_mature')label+=' · '+eur(h.estimated_net_eur)+' ('+pct(h.estimated_return_pct)+')';box.append(el('p',h.hours+'h: '+label));}list.append(box);}
 cards.push(panel(list));return cards;
}