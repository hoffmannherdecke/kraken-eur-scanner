'use strict';
function tradeViewModel(v,current=true){
 const valid=n=>Number.isSafeInteger(n)&&n>=0;
 if(!v||!valid(v.fill_count)||!valid(v.exit_count)||!Array.isArray(v.series)||v.series.length!==1||v.series[0].status!=="active"||!Number.isFinite(Date.parse(v.read_at)))return {available:false};
 const events=(Array.isArray(v.decisions)?v.decisions:[]).filter(d=>d&&((d.phase==="PAPER_FILL"&&d.result==="PAPER_FILLED")||(d.phase==="PAPER_EXIT"&&d.result==="CLOSED")));
 return {available:true,current,fillCount:v.fill_count,exitCount:v.exit_count,events,windowHours:v.window_hours,readAt:v.read_at,series:v.series[0].series_id};
}
function renderTrade(v,current=true){
 const m=tradeViewModel(v,current);
 if(!m.available){put('trade-info',panel(el('h3','Handelsdaten nicht eindeutig','warn'),el('p','Keine aktive Serie oder kein gültiger Cloud-Beleg.')));return;}
 const metrics=el('div',undefined,'metrics');
 metrics.append(metric(m.fillCount,'Belegte Paper-Einstiege'),metric(m.exitCount,'Belegte Paper-Abschlüsse'));
 const cards=[panel(el('h3',m.current?'Handelsbelege der aktiven Serie':'Letzter erfolgreicher Abruf',m.current?'blue':'warn'),el('p','Zeitraum: '+(m.windowHours===24?'letzte 24 Stunden':'Cloud-Abfragezeitraum')),el('small','Stand: '+time(m.readAt)),el('small','Alle Werte betreffen simulierten Handel und sind keine Echtgeldgeschäfte.')),metrics,
 panel(el('h3','Offene Positionen: nicht belegt','warn'),el('p','Die aktuelle Cloud-Schnittstelle enthält keinen vollständigen Positionsbestand. Einstiegs- und Abschlussereignisse sind keine verlässliche Anzahl aktuell offener Positionen.')),
 panel(el('h3','Nettoergebnis im 24-Stunden-Fenster: nicht separat ausgewiesen','muted'),el('p',m.exitCount===0?'Im abgefragten Zeitraum gibt es keine Abschlussbelege.':'Die Zähler oben enthalten keine separate Nettoauswertung für dieses Zeitfenster.'),el('small','Die Wirtschaftsauswertung der gesamten Serie steht getrennt weiter unten. Nachbetrachtungen sind keine realisierten Gewinne.'))];
 cards.push(el('h2','Letzte belegte Handelsereignisse'));
 if(m.events.length)cards.push(...m.events.map(candidate));else cards.push(panel(el('p',m.fillCount===0&&m.exitCount===0?'Keine Einstiegs- oder Abschlussereignisse im abgefragten Zeitraum.':'In der aktuellen Liste der letzten Kandidatenentscheidungen ist kein Handelsbeleg enthalten. Die Zähler oben beziehen sich auf alle Ereignisse im Zeitraum.','muted')));
 cards.push(panel(el('small','Die Liste zeigt nur Handelsereignisse, die zugleich der zuletzt übermittelte Entscheidungsstand eines der höchstens 30 angezeigten Kandidaten sind. Sie ist kein vollständiges Handelsbuch. Noch nicht synchronisierte Vorgänge sind nicht enthalten.')));
 put('trade-info',...cards,...economicPanels(v,current));
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
 if(!m)return [panel(el('h3','Wirtschaftsauswertung der gesamten Serie','warn'),el('p','Der vorhandene Cloud-Zugang liefert noch keinen bestätigten vollständigen Serienexport. Die 24-Stunden-Handelsbelege oben bleiben verfügbar.'))];
 const l=m.ledger,s=l.stats,eur=x=>typeof x==='number'?new Intl.NumberFormat('de-DE',{style:'currency',currency:'EUR',maximumFractionDigits:6}).format(x):'Nicht belegt',pct=x=>typeof x==='number'?new Intl.NumberFormat('de-DE',{maximumFractionDigits:3}).format(x)+' %':'Nicht belegt';
 const cards=[panel(el('h3',m.current?'Wirtschaftliche Belege der gesamten aktiven Serie':'Letzter erfolgreicher Wirtschaftsdatenabruf',m.current?'blue':'warn'),el('small','Stand: '+time(l.read_at)),el('p',l.receipt_count+' Cloud-Journalbelege · '+s.candidate_count+' Kandidaten'),el('p','Erstentscheidungen: '+s.initial.WAIT+' WAIT · '+s.initial.REJECT+' REJECT · '+s.initial.BUY_SCOUT+' BUY · '+s.initial.UNKNOWN+' unklar'),el('small','Nicht synchronisierte lokale Belege fehlen.')),panel(el('h3','Virtuelle Handelsbelege'),el('p','Einstiege: '+s.entry_count+' · Abschlüsse: '+s.exit_count),el('p','Einstiegsbelege ohne Abschlussbeleg: '+s.entry_without_exit_count),el('p','Aktuell offene Positionen: nicht nachgewiesen','warn'),el('p','Belegtes Netto aus Abschlüssen: '+eur(s.net_eur)),el('small','Unklare Kandidaten: '+s.unclear_candidates+'. Keine realen Börsenausführungen.'))];
 for(const h of l.horizons)cards.push(panel(el('h3',h.hours+'-Stunden-Nachbetrachtung'),el('p','Gereifte virtuelle Schätzungen: '+h.estimated_paper_mature+' · Kursbeobachtungen ohne Einstieg: '+h.no_buy_mature),el('p','Noch nicht fällig: '+h.not_due+' · fehlend/ungeklärt: '+h.missing_or_unresolved+' · Datenlücken: '+h.censored+' · widersprüchlich: '+h.conflict),el('small','Keine Addition verschiedener Zeitfenster zu einem Gewinn.')));
 const list=el('details');list.append(el('summary','Einzelne Kandidaten (maximal 30)'));
 for(const c of l.candidates){const box=panel(el('h3',c.pair),el('small','Erstentscheidung: '+c.initial_decision));if(c.entry_at)box.append(el('p','Virtueller Einstieg: '+eur(c.entry_ask_eur)+' · Menge '+c.entry_qty+' · Gebühr '+eur(c.entry_fee_eur)));if(c.exit_at)box.append(el('p','Abschlussbeleg: '+eur(c.exit_net_eur)));for(const h of c.followups){let label={no_buy_mature:'Kursentwicklung ohne Einstieg',estimated_paper_mature:'Geschätztes Paper-Netto',not_due:'Noch nicht fällig',censored:'Datenlücke',conflict:'Widersprüchlich',missing_or_unresolved:'Fehlend oder ungeklärt'}[h.status];if(h.status==='no_buy_mature')label+=' · Hoch '+pct(h.mfe_pct)+' · Tief '+pct(h.mae_pct)+' · Ende '+pct(h.close_return_pct);if(h.status==='estimated_paper_mature')label+=' · '+eur(h.estimated_net_eur)+' ('+pct(h.estimated_return_pct)+')';box.append(el('p',h.hours+'h: '+label));}list.append(box);}
 cards.push(panel(list));return cards;
}
