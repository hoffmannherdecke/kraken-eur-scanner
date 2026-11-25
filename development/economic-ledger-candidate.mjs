// Pure, offline candidate. No network, credentials, database writes, or runtime controls.
export function buildEconomicLedger(input){
 const fail=reason=>({kind:"KRYPTO_ECONOMIC_LEDGER_V1",status:"UNAVAILABLE",reason});
 const finite=v=>typeof v==="number"&&Number.isFinite(v),num=v=>finite(v)?v:null;
 const clock=v=>typeof v==="string"?Date.parse(v):NaN;
 const positive=v=>finite(v)&&v>0;
 const {series_id:s,read_at:at,active_count:active,exact_count:total,rows}=input||{};
 if(active!==1||typeof s!=="string"||!/^PAPER-V3-\d{8}T\d{6}Z$/.test(s)||!Number.isFinite(clock(at))||!Number.isSafeInteger(total)||total<0||total>5000||!Array.isArray(rows)||rows.length!==total)return fail("INCOMPLETE_OR_AMBIGUOUS_SERIES");
 const ids=new Set(),groups=new Map(),revisions=new Set();
 for(const r of rows){
  if(!r||r.series_id!==s||typeof r.revision!=="string"||!r.revision.startsWith("V3-")||typeof r.event_id!=="string"||!/^[0-9a-f]{64}$/.test(r.event_id)||ids.has(r.event_id)||typeof r.candidate_id!=="string"||!r.candidate_id||typeof r.pair!=="string"||!r.pair.endsWith("/EUR")||!Number.isFinite(clock(r.source_known_at))||!Number.isFinite(clock(r.received_at))||!Number.isFinite(clock(r.event_time_utc))||clock(r.event_time_utc)>clock(r.source_known_at)||clock(r.source_known_at)>clock(at)||clock(r.received_at)>clock(at))return fail("INVALID_RECEIPT_IDENTITY_OR_CLOCK");
  ids.add(r.event_id);revisions.add(r.revision);
  let g=groups.get(r.candidate_id);
  if(!g){g={pair:r.pair,rows:[],conflict:false};groups.set(r.candidate_id,g);}
  if(g.pair!==r.pair)g.conflict=true;g.rows.push(r);
 }
 if(revisions.size>1)return fail("AMBIGUOUS_REVISION");
 const stats={candidate_count:groups.size,initial:{WAIT:0,REJECT:0,BUY_SCOUT:0,UNKNOWN:0},entry_count:0,entry_without_exit_count:0,exit_count:0,unclear_candidates:0,net_eur:null,closed_with_net_count:0};
 const horizons=[6,24,72].map(hours=>({hours,no_buy_mature:0,estimated_paper_mature:0,censored:0,not_due:0,missing_or_unresolved:0,conflict:0}));
 const candidates=[];let net=0,netInvalid=false;
 for(const [candidate_id,g] of groups){
  const a=g.rows,anchors=a.filter(r=>["SCANNER_CAPTURE","P1_CHILD_ENROLLMENT"].includes(r.phase)&&r.result==="SEEN");
  const initial=a.filter(r=>r.phase==="P4_VALIDATION");
  const d=initial.length===1&&["WAIT","REJECT","BUY_SCOUT","UNKNOWN"].includes(initial[0].result)?initial[0].result:"UNKNOWN";
  stats.initial[d]++;
  const fills=a.filter(r=>r.phase==="PAPER_FILL"),exits=a.filter(r=>r.phase==="PAPER_EXIT");
  const f=fills.length===1?fills[0]:null,x=exits.length===1?exits[0]:null;
  const fillOk=f&&f.result==="PAPER_FILLED"&&f.source_status==="ASSUMED_VIRTUAL_PAPER_ASK_NOT_REAL_EXCHANGE_FILL"&&positive(f.paper_entry_ask_eur)&&positive(f.paper_entry_qty)&&finite(f.paper_entry_fee_eur)&&f.paper_entry_fee_eur>=0&&d==="BUY_SCOUT"&&clock(initial[0].source_known_at)<=clock(f.source_known_at);
  const exitOk=x&&fillOk&&x.result==="CLOSED"&&clock(x.source_known_at)>=clock(f.source_known_at);
  const conflict=g.conflict||anchors.length>1||initial.length>1||fills.length>1||exits.length>1||!!f&&!fillOk||!!x&&!exitOk||(d==="BUY_SCOUT"&&!fillOk);
  let status=conflict?"UNCLEAR":exitOk?"EXIT_RECORDED":fillOk?"ENTRY_WITHOUT_EXIT_RECEIPT":"NO_ENTRY_RECEIPT";
  if(conflict){stats.unclear_candidates++;netInvalid=true;}
  if(!conflict&&fillOk){stats.entry_count++;if(!exitOk)stats.entry_without_exit_count++;}
  if(!conflict&&exitOk){stats.exit_count++;if(finite(x.position_net_pnl_eur)){stats.closed_with_net_count++;net+=x.position_net_pnl_eur;}else netInvalid=true;}
  const anchor=anchors.length===1?anchors[0]:null;
  const out=[];
  for(const h of horizons){
   const rr=a.filter(r=>r.phase==="FOLLOWUP_"+h.hours+"H"&&["MATURE_COMPLETE","CENSORED"].includes(r.result));
   const r=rr.length===1?rr[0]:null;
   const start=fillOk?clock(f.source_known_at):clock(anchor?.event_time_utc);
   let category,values={};
   if(conflict||rr.length>1)category="conflict";
   else if(r){
    const noBuy=r.source_status==="NO_BUY_OPPORTUNITY_LABEL_NOT_EXECUTABLE_TRADED_PNL";
    const typeMatches=fillOk?!noBuy:noBuy;
    const timing=anchor&&Number.isFinite(start)&&clock(r.event_time_utc)===clock(anchor.event_time_utc)&&clock(r.source_known_at)>=start+h.hours*3600000;
    if(!typeMatches||!timing||r.followup_source!=="KRAKEN_CLOSED_1M_PATH_CAPTURE_V1")category="conflict";
    else if(r.result==="CENSORED")category=typeof r.censor_reason==="string"&&r.censor_reason?"censored":"conflict";
    else if(r.path_contiguous_1m_verified!==true)category="conflict";
    else if(noBuy){
     if(r.position_net_pnl_eur!=null||r.position_net_return_pct!=null||![r.mfe_pct,r.mae_pct,r.close_return_pct].every(finite))category="conflict";
     else{category="no_buy_mature";values={mfe_pct:r.mfe_pct,mae_pct:r.mae_pct,close_return_pct:r.close_return_pct};}
    }else if(fillOk&&finite(r.position_net_pnl_eur)&&finite(r.position_net_return_pct)){category="estimated_paper_mature";values={estimated_net_eur:r.position_net_pnl_eur,estimated_return_pct:r.position_net_return_pct,mfe_pct:num(r.mfe_pct),mae_pct:num(r.mae_pct)};}
    else category="conflict";
   }else if(Number.isFinite(start)&&clock(at)<start+h.hours*3600000)category="not_due";
   else category="missing_or_unresolved";
   h[category]++;out.push({hours:h.hours,status:category,...values,...(category==="censored"?{reason:r.censor_reason}: {})});
  }
  candidates.push({candidate_id,pair:g.pair,initial_decision:d,status,entry_at:!conflict&&fillOk?f.source_known_at:null,entry_ask_eur:!conflict&&fillOk?f.paper_entry_ask_eur:null,entry_qty:!conflict&&fillOk?f.paper_entry_qty:null,entry_fee_eur:!conflict&&fillOk?f.paper_entry_fee_eur:null,exit_at:!conflict&&exitOk?x.source_known_at:null,exit_bid_eur:!conflict&&exitOk?num(x.paper_exit_bid_eur):null,exit_net_eur:!conflict&&exitOk?num(x.position_net_pnl_eur):null,followups:out,last_known_at:a.reduce((v,r)=>!v||clock(r.source_known_at)>clock(v)?r.source_known_at:v,null)});
 }
 if(!netInvalid&&stats.exit_count>0&&stats.closed_with_net_count===stats.exit_count)stats.net_eur=Number(net.toFixed(6));
 candidates.sort((a,b)=>clock(b.last_known_at)-clock(a.last_known_at)||a.candidate_id.localeCompare(b.candidate_id));
 return {kind:"KRYPTO_ECONOMIC_LEDGER_V1",status:"COMPLETE_CLOUD_RECEIPTS_ONLY",series_id:s,read_at:at,revision:[...revisions][0]??null,receipt_count:total,stats,horizons,candidates:candidates.slice(0,30),candidate_list_limit:30,live_positions_verified:false,real_money:false};
}
