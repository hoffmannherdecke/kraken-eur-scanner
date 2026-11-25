'use strict';
function learningSample(v,current=true){
 const valid=n=>Number.isSafeInteger(n)&&n>=0;
 if(!v||!Array.isArray(v.series)||v.series.length!==1||v.series[0].status!=="active"||!Number.isFinite(Date.parse(v.read_at))||!valid(v.candidate_count)||!valid(v.fill_count)||!valid(v.exit_count)||!Array.isArray(v.decisions))return null;
 const counts={WAIT:0,REJECT:0,BUY_SCOUT:0,other:0};
 for(const d of v.decisions){if(d&&["WAIT","REJECT","BUY_SCOUT"].includes(d.result))counts[d.result]++;else counts.other++;}
 return {series:v.series[0].series_id,readAt:v.read_at,current,windowHours:v.window_hours,candidates:v.candidate_count,fills:v.fill_count,exits:v.exit_count,listed:v.decisions.length,counts};
}
function lessonModel(matrix,bundle){
 if(matrix?.kind!=="V3_NO_BUY_LESSONS_IMPLEMENTATION_MATRIX_V1"||!Array.isArray(matrix.lessons)||bundle?.kind!=="V3_EXPERIMENTAL_PAPER_ALL_LESSONS_POLICY_BUNDLE_V1"||!Array.isArray(bundle.entry_priority)||!matrix.lessons.every(l=>typeof l.id==="string"&&typeof l.disposition==="string")||!bundle.entry_priority.every(l=>typeof l.id==="string"&&typeof l.paper_policy_selected==="boolean"))throw Error("Unrecognized learning source");
 const selected=bundle.entry_priority.filter(l=>l.paper_policy_selected===true).map(l=>l.id);
 return {lessons:matrix.lessons,selected,revision:bundle.strategy_revision};
}
function releaseModel(v,activeSeries){
 const r=v?.operational_release_snapshot;
 if(r?.kind!=="LAST_VERIFIED_OPERATIONAL_RELEASE_NOT_LIVE_STATUS"||!Number.isFinite(Date.parse(r.observed_at_utc))||typeof r.series_id!=="string"||typeof r.release_milestone!=="string")return null;
 return {series:r.series_id,observed:r.observed_at_utc,milestone:r.release_milestone,economic:r.economic_qualification,matching:r.series_id===activeSeries,revision:r.strategy_revision};
}
const LEARN_REPO='https://github.com/hoffmannherdecke/kraken-eur-scanner';
const LEARN_RAW='https://raw.githubusercontent.com/hoffmannherdecke/kraken-eur-scanner/main/';
const LEARN_PATHS=['research/v3/v3-buy-decision-lessons-implementation-matrix-20261011.json','research/v3/v3-experimental-paper-all-lessons-bundle-20261011.json','project-current-state.json'];
const LESSON_TEXT={
 NULL_BUY_ECONOMIC:['Zu wenige Einstiege','Bisherige Strategien erzielten kaum oder keine Paper-Einstiege. Wirtschaftlicher Erfolg muss separat nachgewiesen werden.'],
 EXTENDED_LATE_CHASE:['Neue Chance nach starkem Anstieg','Ein früherer Anstieg soll einen späteren eigenständigen Einstieg nicht dauerhaft ausschließen.'],
 SECOND_LEG:['Zweiter Aufwärtsimpuls','Eine neue Konsolidierung und ein bestätigter Ausbruch können eine erneute Prüfung begründen.'],
 BAD_NOW_NOT_DEAD:['Jetzt ungeeignet heißt nicht dauerhaft ungeeignet','Eine spätere neue Marktsituation kann erneut bewertet werden.'],
 BREAKOUT_RESISTANCE:['Widerstand und Ausbruch','Ein neuer Ausbruch soll strukturell bestätigt werden.'],
 WAIT_TTL_NEVER_RECHECK:['Wartezeit und Nachprüfung','Viele frühere WAIT-Fälle liefen ohne erneute Modellprüfung ab. Schnellere Prüfungen allein beweisen keinen besseren Einstieg.'],
 OVERSTRICT_ENTRY_MODEL:['Zu strenge Einstiegslogik','Eine neue Prüfung ist noch kein Kauf; die Handelsqualität muss belegt werden.'],
 COIN_ENTRY_FEATURE_GAP:['Bessere Coin-Daten','Kurse, Kerzen, Volumen, ATR und Struktur des einzelnen Coins sollen zeitgerecht in die Prüfung eingehen.'],
 COIN_ATTACH_2_OF_4:['Technische Datenlücken','Technische Fehler und fehlende Eingabedaten dürfen nicht als wirtschaftliche Ablehnung gelten.'],
 OPTIONAL_SOURCE_NEUTRAL:['Optionale Informationsquellen','Fehlende Nachrichten oder Zusatzquellen sollen kein automatisches Kaufverbot auslösen.'],
 SOFT_FACTORS_COMPENSATE:['Abwägung weicher Faktoren','Nicht jede weiche Warnung muss ein unabhängiges Ausschlusskriterium sein.'],
 TRADABILITY_KRAKEN_LIVE:['Tatsächliche Handelbarkeit','Öffentliche Kraken-EUR-Handelbarkeit ist die Paper-Referenz.'],
 FEES_AND_EXECUTION:['Gebühren und Ausführung','Kursbewegung allein ist kein Gewinn; Kosten und Ausführung müssen berücksichtigt werden.'],
 STOP_STAGE2:['Risikoplan und zweiter Einstieg','Ein gültiger Stop und ein sinnvoller zweiter Einstieg bleiben erforderlich.'],
 SCANNER_SCORE:['Scanner-Bewertung','Der Scanner-Score allein rechtfertigt weder Kauf noch Positionsgröße.'],
 CHRONOLOGY_MFE_MAE:['Kursverlauf statt bloßem Höchstkurs','Spätere Höchstkurse und Verluste müssen in ihrer zeitlichen Reihenfolge bewertet werden.'],
 REGIME_HETEROGENEITY:['Unterschiedliche Marktphasen','Ergebnisse sollen nach Marktumfeld getrennt untersucht werden.'],
 SOURCES_H2_H11:['Zusatzquellen prüfen','Mehrwert externer Quellen muss einzeln belegt werden.'],
 ACTIVATION_SAFE:['Getrennte Betriebsfreigabe','Forschung und Echtgeldfreigabe bleiben getrennt.']
};
const DISPOSITION_TEXT={ESTABLISHED_UNRESOLVED:'Befund belegt, Lösung wirtschaftlich offen',INACTIVE_REVIEW_POLICY_IMPLEMENTED:'Historischer Entwicklungsstand: Prüfregel programmiert',INACTIVE_REVIEW_POLICY_IMPLEMENTED_NOT_TRADE_PROVEN:'Historische Prüfregel programmiert, Handelserfolg nicht belegt',PARTIAL_B_AND_LATER_EVALUATOR:'Damals teilweise umgesetzt',MECHANIC_INHERITED_V2R4_ECONOMIC_NOT_FIXED:'Mechanik übernommen, wirtschaftliche Wirkung offen',DECISION_CHANGE_DRAFT_IMPLEMENTED_ECONOMIC_NOT_PROVEN:'Entwurf umgesetzt, Wirkung nicht belegt',INPUT_ADAPTER_PREPARED_PHYSICAL_PARTIAL:'Damals Datenanbindung vorbereitet',KNOWN_UNDIAGNOSED_LIVE_CASES:'Damals offene Einzelfälle',RESEARCH_POLICY_IMPLEMENTED_OPTIONAL:'Kontextregel im Forschungsstand umgesetzt',CONTINUE_FOR_FULL_MODEL_LATER:'Weitere Prüfung vorgesehen',INHERITED_V2R4_REQUIRE_LIVE_RECHECK:'Handelbarkeit erneut zu prüfen',HARD_GUARD_INHERITED:'Bestehende Risikoanforderung übernommen',OVERRIDE_REJECTED:'Automatische Übersteuerung verworfen',MEASUREMENT_REQUIRED:'Wirtschaftliche Messung erforderlich',FUTURE_STRATIFICATION:'Getrennte Auswertung vorgesehen',SEPARATELY_GATED_FOR_COMBINED_V3:'Separater Nachweis erforderlich',UNCHANGED_INHERITED_HARD_GATE:'Bestehende Freigabegrenze unverändert'};
const FAMILY_TEXT={SOURCE_CATALYST_INDEPENDENT:'Einstiegskandidat aus belegtem positivem Ereignis',FIRST_SCANNER_EARLY_REVIEW:'Frühere vollständige Kandidatenprüfung',CONTINUITY_FRESH_5M:'Neue 5-Minuten-Bestätigung',P3_CONTINUITY_15M_STANDARD:'Neue 15-Minuten-Bestätigung',WAIT_EXPIRED_FRESH_REENTRY:'Neue Prüfung nach abgelaufenem WAIT',EXTENDED_GENUINE_NEW_BASE:'Neue Basis nach starkem Anstieg',CONTINUITY_VOLUME_RESEARCH_ONLY:'Getrennte Volumenhypothese'};
function learnLink(label,path){const a=el('a',label,'blue');a.href=LEARN_REPO+'/blob/main/'+path;a.target='_blank';a.rel='noopener noreferrer';return a;}
function renderLearning(v,current=true){
 const m=learningSample(v,current);
 if(!m){put('learn-current',panel(el('h3','Aktuelle Lernbasis nicht verfügbar','warn')));return;}
 const metrics=el('div',undefined,'metrics');metrics.append(metric(m.candidates,'Erfasste Kandidaten'),metric(m.fills,'Belegte Einstiege'));
 const p=panel(el('h3',m.current?'Aktuelle Paper-Lernbasis':'Letzter erfolgreicher Datenabruf',m.current?'blue':'warn'),el('small','Stand: '+time(m.readAt)),el('p','Zeitraum: '+(m.windowHours===24?'letzte 24 Stunden':'Cloud-Abfragezeitraum')),metrics,el('p','Abschlussbelege: '+m.exits),el('p','In den '+m.listed+' angezeigten letzten Kandidatenentscheidungen: '+m.counts.WAIT+' WAIT, '+m.counts.REJECT+' REJECT, '+m.counts.BUY_SCOUT+' BUY-Freigaben, '+m.counts.other+' andere Zustände.'),el('small','Entscheidungsstände sind keine vollständige Konversionsstatistik. Die vorhandene Schnittstelle enthält keine vollständigen 6-/24-/72-Stunden-Nachbetrachtungen. Keine Aussage über aktuell verpasste Gewinne oder bewiesene Verbesserung.'));
 put('learn-current',p);
 if(learnRelease)renderLearningRelease(v);
}
let learnRelease=null;
function renderLearningRelease(v){
 const r=releaseModel(learnRelease,learningSample(v)?.series);
 if(!r){put('learn-release',panel(el('h3','Release-Nachweis nicht verfügbar','warn')));return;}
 const p=panel(el('h3','Letzter dokumentierter Entwicklungsmeilenstein'),el('p',r.milestone==='V3_PAPER_OPERATIONAL'?'V3-Paper-Betriebsabnahme dokumentiert':r.milestone,'blue'),el('small','Originalstand: '+time(r.observed)),el('p',r.matching?'Gehört zur derzeit in der App ausgewiesenen Serie.':'Andere oder nicht eindeutig zugeordnete Serie.'),el('p',r.economic==='NOT_DEMONSTRATED_BY_AP06B'?'Die Betriebsabnahme belegt keine wirtschaftliche Qualifikation.':'Wirtschaftliche Qualifikation nicht aus dem Meilenstein ableiten.','warn'),el('small','Datiertes Release-Ereignis, keine Aussage über die momentane Runtime.'),learnLink('Projektstatus / Originalverweise','project-current-state.json'));
 put('learn-release',p);
}
function renderLessons(m){
 const p=panel(el('h3','Dokumentierte Verbesserungsansätze'),el('p',m.lessons.length+' Lernpunkte · historische Matrix vom 11.10.2026'),el('small','Dies ist die damalige Entwicklungsentscheidung, nicht der aktuelle Implementierungs- oder Erfolgsnachweis.'));
 const d=el('details');d.append(el('summary','Alle Lernpunkte anzeigen'));
 for(const l of m.lessons){const t=LESSON_TEXT[l.id];const r=el('div',undefined,'split');const a=el('div');a.append(el('h3',t?.[0]||l.id),el('p',t?.[1]||'Siehe Originalbefund.','sub'),el('p',DISPOSITION_TEXT[l.disposition]||'Historischer Status: '+l.disposition,'blue'),detail('Originalbefund',String(l.finding||'')+' | '+String(l.implementation||'')));r.append(a);d.append(r);}
 p.append(d,learnLink('Originale Lernmatrix',LEARN_PATHS[0]));
 const b=panel(el('h3','Ausgewählte V3-Strategieansätze'),el('p',m.selected.length+' ausgewählte Prüfpfade im dokumentierten Konzept'),el('small','Auswahl im Konzept ist kein Beweis einer produktiven Einzelnutzung oder einer wirtschaftlichen Verbesserung.'));
 for(const id of m.selected)b.append(el('p','• '+(FAMILY_TEXT[id]||id),'sub'));
 b.append(learnLink('Originales V3-Konzept',LEARN_PATHS[1]));
 put('learn-lessons',p,b);
}
let learningBusy=false,learningLoaded=false,learningGeneration=0;
async function learnJSON(path){
 const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),12000);
 try{const r=await fetch(LEARN_RAW+path,{credentials:'omit',referrerPolicy:'no-referrer',cache:'no-cache',signal:controller.signal});if(!r.ok)throw Error('Read failed');return r.json();}finally{clearTimeout(timer);}
}
function resetLearning(){learningGeneration++;learningBusy=false;learningLoaded=false;learnRelease=null;$('learn-refresh').disabled=false;$('learn-note').textContent='Originalberichte werden beim Öffnen gelesen.';for(const id of ['learn-current','learn-release','learn-lessons'])$(id).replaceChildren();}
async function loadLearning(){
 if(learningBusy||!data)return;
 learningBusy=true;const generation=learningGeneration;$('learn-refresh').disabled=true;$('learn-note').textContent='Originale Lernnachweise werden gelesen …';
 const r=await Promise.allSettled(LEARN_PATHS.map(learnJSON));
 if(generation!==learningGeneration)return;
 let complete=true;
 try{if(r[0].status!=='fulfilled'||r[1].status!=='fulfilled')throw Error('Missing learning source');renderLessons(lessonModel(r[0].value,r[1].value));}catch{complete=false;put('learn-lessons',panel(el('h3','Historische Lernnachweise derzeit nicht verfügbar','warn')));}
 try{if(r[2].status!=='fulfilled'||!releaseModel(r[2].value,learningSample(data)?.series))throw Error('Missing release');learnRelease=r[2].value;renderLearningRelease(data);}catch{complete=false;learnRelease=null;put('learn-release',panel(el('h3','Entwicklungsmeilenstein derzeit nicht verfügbar','warn')));}
 $('learn-note').textContent=complete?'Originalquellen gelesen: '+time(new Date().toISOString()):'Abruf unvollständig. Bitte bei Bedarf erneut versuchen.';
 learningLoaded=complete;learningBusy=false;$('learn-refresh').disabled=false;
}
document.querySelector('nav button[data-page="learning"]').addEventListener('click',()=>{if(!learningLoaded)loadLearning();});
$('learn-refresh').addEventListener('click',loadLearning);
