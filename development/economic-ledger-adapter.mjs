// Staged adapter only. Receives the existing approved reader; no HTTP handler, credentials or deployment.
import {buildEconomicLedger} from './economic-ledger-candidate.mjs';
async function readEconomicInput(read,series,at){
 if(!Array.isArray(series)||series.length!==1||series[0]?.status!=="active"||!/^PAPER-V3-\d{8}T\d{6}Z$/.test(series[0]?.series_id||"")||!Number.isFinite(Date.parse(at)))return null;
 const sid=series[0].series_id;
 const fields=["p4_decision","paper_entry_ask_eur","paper_entry_qty","paper_entry_fee_eur","paper_exit_bid_eur","paper_exit_fee_eur","position_net_pnl_eur","position_net_return_pct","followup_source","path_contiguous_1m_verified","source_status","mfe_pct","mae_pct","close_return_pct","censor_reason"];
 const params={select:"event_id,series_id,revision,candidate_id,pair,phase,result,source_known_at,received_at,event_time_utc:payload->>event_time_utc,"+fields.map(f=>f+":payload->data->"+f).join(","),series_id:"eq."+sid,received_at:"lte."+at,order:"source_known_at.asc,received_at.asc,event_id.asc",limit:"500"};
 try{
 const first=await read("v3_paper_event_receipts",params,true);
 if(!Number.isSafeInteger(first?.total)||first.total<0||first.total>5000||!Array.isArray(first.rows)||first.rows.length!==Math.min(500,first.total))return null;
 const rows=[...first.rows];
 while(rows.length<first.total){const p=await read("v3_paper_event_receipts",{...params,offset:String(rows.length)});if(!Array.isArray(p?.rows)||p.rows.length!==Math.min(500,first.total-rows.length))return null;rows.push(...p.rows);}
 if(rows.some(r=>!r||r.series_id!==sid||typeof r.event_id!=="string")||new Set(rows.map(r=>r.event_id)).size!==first.total)return null;
 return {series_id:sid,read_at:at,active_count:1,exact_count:first.total,rows};
 }catch{return null;}
}
export async function economicProjection(existingRead,series,at){return buildEconomicLedger(await readEconomicInput(existingRead,series,at));}
