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
 panel(el('h3','Nettoergebnis: noch nicht verfügbar','muted'),el('p',m.exitCount===0?'Im abgefragten Zeitraum gibt es keine Abschlussbelege. Ohne Abschlussnachweis wird kein Gewinn oder Verlust ausgewiesen.':'Die vorhandene App-Schnittstelle liefert noch keine Nettoergebnisse zu den Abschlüssen.'),el('small','6-, 24- und 72-Stunden-Nachbetrachtungen sind Schätzungen auf Basis des Kursverlaufs, keine realisierten Gewinne.'))];
 cards.push(el('h2','Letzte belegte Handelsereignisse'));
 if(m.events.length)cards.push(...m.events.map(candidate));else cards.push(panel(el('p',m.fillCount===0&&m.exitCount===0?'Keine Einstiegs- oder Abschlussereignisse im abgefragten Zeitraum.':'In der aktuellen Liste der letzten Kandidatenentscheidungen ist kein Handelsbeleg enthalten. Die Zähler oben beziehen sich auf alle Ereignisse im Zeitraum.','muted')));
 cards.push(panel(el('small','Die Liste zeigt nur Handelsereignisse, die zugleich der zuletzt übermittelte Entscheidungsstand eines der höchstens 30 angezeigten Kandidaten sind. Sie ist kein vollständiges Handelsbuch. Noch nicht synchronisierte Vorgänge sind nicht enthalten.')));
 put('trade-info',...cards);
}
