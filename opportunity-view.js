'use strict';
function opportunityViewModel(v,current=true){
 const model=economicViewModel(v,current);
 if(!model)return null;
 const l=model.ledger;
 const horizons=[];
 const cats=["no_buy_mature","estimated_paper_mature","censored","not_due","missing_or_unresolved","conflict"];
 const num=x=>typeof x==="number"&&Number.isFinite(x);
 for(const h of l.horizons){
  const counts=Object.fromEntries(cats.map(k=>[k,0])),rows=[];
  for(const c of l.candidates){
   const f=c.followups.find(x=>x.hours===h.hours);
   if(!f)return null;
   counts[f.status]++;
   if(f.status!=="no_buy_mature")continue;
   if(c.status!=="NO_ENTRY_RECEIPT"||![f.mfe_pct,f.mae_pct,f.close_return_pct].every(num)||f.mae_pct>0||f.mfe_pct<0||f.mae_pct>f.close_return_pct||f.close_return_pct>f.mfe_pct)return null;
   rows.push({candidateId:c.candidate_id,pair:c.pair,decision:c.initial_decision,high:f.mfe_pct,low:f.mae_pct,close:f.close_return_pct});
  }
  if(cats.some(k=>counts[k]>h[k]||(l.candidates.length===l.stats.candidate_count&&counts[k]!==h[k])))return null;
  rows.sort((a,b)=>b.close-a.close||a.pair.localeCompare(b.pair)||a.candidateId.localeCompare(b.candidateId));
  horizons.push({hours:h.hours,mature:h.no_buy_mature,notDue:h.not_due,unresolved:h.missing_or_unresolved,censored:h.censored,conflict:h.conflict,estimated:h.estimated_paper_mature,rows,notShown:h.no_buy_mature-rows.length});
 }
 return {current:model.current,readAt:l.read_at,candidateCount:l.stats.candidate_count,horizons};
}

function opportunityPanels(v,current=true){
 const m=opportunityViewModel(v,current);
 if(!m)return [panel(el('h3','Chancenanalyse – noch keine vollständige Datengrundlage','warn'),el('p','Die App benötigt die originalen 6-, 24- und 72-Stunden-Nachbetrachtungen der aktiven Serie. Ohne bestätigten vollständigen Serienexport werden weder verpasste Gewinne noch Nullwerte behauptet.'))];
 const pct=x=>(x>0?'+':'')+new Intl.NumberFormat('de-DE',{maximumFractionDigits:3}).format(x)+' %';
 const p=panel(el('h3','Kursentwicklung ohne Einstieg',m.current?'blue':'warn'),el('small','Stand: '+time(m.readAt)),el('p','Referenz ist der Schlusskurs der ersten vollständigen 1-Minuten-Kerze nach dem ursprünglichen Ereignis. Hoch, Tief und Ende sind Kursbeobachtungen, keine ausführbaren Einstiege, kein Gewinn und kein Beweis einer Fehlentscheidung.'));
 if(!m.current)p.append(el('p','Letzter erfolgreicher Abruf – nicht aktuell.','warn'));
 for(const h of m.horizons){
 const d=el('details');d.append(el('summary',h.hours+' Stunden · '+h.mature+' reife Beobachtungen ohne Einstieg'));
 d.append(el('p','Noch nicht fällig: '+h.notDue+' · fehlend/ungeklärt: '+h.unresolved+' · Datenlücken: '+h.censored+' · widersprüchlich: '+h.conflict+' · virtuelle Einstiegs-Nachbetrachtungen: '+h.estimated,'sub'));
 if(!h.mature)d.append(el('p','Keine reifen Beobachtungen ohne Einstieg in diesem Zeitfenster.','muted'));
 else{
 d.append(el('p','Angezeigter Ausschnitt: '+h.rows.length+' von '+h.mature+' reifen Beobachtungen. Sortiert nach Schlussentwicklung, positiv und negativ.','sub'));
 for(const r of h.rows){const x=el('div',undefined,'split'),b=el('div');b.append(el('h3',r.pair),el('small','Erstentscheidung: '+r.decision),el('p','Ende '+pct(r.close)+' · Hoch '+pct(r.high)+' · Tief '+pct(r.low)));x.append(b);d.append(x);}
 if(h.notShown)d.append(el('p',h.notShown+' weitere reife Beobachtungen sind nicht in der begrenzten Kandidatenliste enthalten.','warn'));
 }
 p.append(d);
 }
 p.append(el('small','Zeitfenster getrennt betrachten. Für eine wirtschaftliche Bewertung sind ausführbarer Einstieg, Stop, zeitliche Abfolge und Kosten nötig. Keine Änderung der Strategie.'));
 return [p];
}
