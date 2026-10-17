import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {createClient} from "npm:@supabase/supabase-js@2";

const RELAY_ID="v3-paper-evidence-relay";
const HEX=/^[0-9a-f]{64}$/;
function respond(status:number,body:Record<string,unknown>){
  return new Response(JSON.stringify(body),{status,headers:{"Content-Type":"application/json","Cache-Control":"no-store"}});
}
function asHex(buffer:ArrayBuffer){
  return Array.from(new Uint8Array(buffer)).map(x=>x.toString(16).padStart(2,"0")).join("");
}
async function authorized(admin:any,request:Request):Promise<boolean>{
  const supplied=request.headers.get("X-V3-Paper-Evidence-Token")??"";
  if(supplied.length<24||supplied.length>512)return false;
  const {data,error}=await admin.from("internal_relay_credentials")
    .select("token_sha256,enabled").eq("relay_id",RELAY_ID).maybeSingle();
  if(error||data?.enabled!==true||!HEX.test(data.token_sha256))return false;
  const hashed=asHex(await crypto.subtle.digest("SHA-256",new TextEncoder().encode(supplied)));
  let mismatch=0;
  for(let i=0;i<64;i++)mismatch|=hashed.charCodeAt(i)^data.token_sha256.charCodeAt(i);
  return mismatch===0;
}
function valid(payload:any,series:string,revision:string):boolean{
  if(!payload||typeof payload!=="object"||
    payload.kind!=="V3_EXPERIMENTAL_PAPER_CANDIDATE_EVENT_V1"||
    payload.orders!==false||payload.real_money_actions!==false||
    payload.series_id!==series||payload.revision!==revision||
    typeof payload.candidate_id!=="string"||payload.candidate_id.length>150||
    typeof payload.pair!=="string"||!payload.pair.endsWith("/EUR")||
    typeof payload.phase!=="string"||!/^[A-Z][A-Z0-9_]+$/.test(payload.phase)||
    typeof payload.result!=="string"||!/^[A-Z][A-Z0-9_]+$/.test(payload.result)||
    typeof payload.event_key!=="string"||!/^[A-Z][A-Z0-9_]+$/.test(payload.event_key)||
    typeof payload.known_at_utc!=="string"||!Number.isFinite(Date.parse(payload.known_at_utc))||
    typeof payload.event_time_utc!=="string"||!Number.isFinite(Date.parse(payload.event_time_utc))||
    Date.parse(payload.known_at_utc)<Date.parse(payload.event_time_utc)||
    Date.parse(payload.known_at_utc)>Date.now()+120000)return false;
  if(payload.phase.startsWith("FOLLOWUP_")&&payload.result==="MATURE_COMPLETE"){
    const h=Number(payload.phase.match(/^FOLLOWUP_(6|24|72)H$/)?.[1]??0);
    if(!h||Date.parse(payload.known_at_utc)-Date.parse(payload.event_time_utc)<h*3600000||
      payload.data?.path_contiguous_1m_verified!==true)return false;
  }
  return true;
}
Deno.serve(async(req:Request)=>{
  if(req.method!=="POST")return respond(405,{ok:false,error:"method_not_allowed"});
  const url=Deno.env.get("SUPABASE_URL")??"";
  const secret=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")??"";
  if(!url||!secret)return respond(503,{ok:false,error:"server_config_missing"});
  const db=createClient(url,secret,{auth:{persistSession:false,autoRefreshToken:false}});
  if(!await authorized(db,req))return respond(401,{ok:false,error:"unauthorized"});
  let body:any;
  try{
    if(Number(req.headers.get("content-length")??0)>256000)
      return respond(413,{ok:false,error:"oversized"});
    body=await req.json();
  }catch{return respond(400,{ok:false,error:"invalid_json"});}
  if(body?.action!=="sync_paper_receipts")
    return respond(400,{ok:false,error:"sync_only_no_activation"});
  const sid=String(body.series_id??"");
  const revision=String(body.strategy_revision??"");
  const rows=body.receipts;
  if(!/^PAPER-V3-[A-Za-z0-9_-]+$/.test(sid)||
      revision!=="V3-EXPERIMENTAL-PAPER-20261011-ALL-LESSONS-001"||
      !Array.isArray(rows)||!rows.length||rows.length>30)
    return respond(400,{ok:false,error:"invalid_v3_paper_batch"});
  // Only the exact isolated CANARY namespace may bypass the active Paper-series check.
  // An arbitrary non-CANARY series containing the word CANARY is NOT a trial.
  const canarySeries=/^PAPER-V3-CANARY-[A-Za-z0-9_-]+$/.test(sid);
  if(!canarySeries){
    const {data:active,error}=await db.from("paper_series")
      .select("status,strategy_revision").eq("series_id",sid).maybeSingle();
    if(error||active?.status!=="active"||active?.strategy_revision!==revision)
      return respond(409,{ok:false,error:"real_v3_paper_series_not_active"});
  }
  for(const rec of rows){
    if(!rec||typeof rec!=="object"||!HEX.test(rec.sha256)||
       typeof rec.canonical_json!=="string"||rec.canonical_json.length>16000)
      return respond(400,{ok:false,error:"invalid_source_receipt"});
    const digest=asHex(await crypto.subtle.digest("SHA-256",
      new TextEncoder().encode(rec.canonical_json)));
    if(digest!==rec.sha256)
      return respond(400,{ok:false,error:"source_hash_mismatch"});
    let parsed:any;
    try{parsed=JSON.parse(rec.canonical_json);}
    catch{return respond(400,{ok:false,error:"canonical_receipt_invalid_json"});}
    if(!valid(parsed,sid,revision))
      return respond(400,{ok:false,error:"unsafe_receipt"});
    const stable=[parsed.series_id,parsed.candidate_id,parsed.phase,parsed.event_key].join("|");
    const calculated=asHex(await crypto.subtle.digest("SHA-256",
       new TextEncoder().encode(stable)));
    if(rec.event_id!==calculated)
      return respond(400,{ok:false,error:"event_identity_mismatch"});
  }
  let accepted=0;
  for(const rec of rows){
    const payload=JSON.parse(rec.canonical_json);
    const row={event_id:rec.event_id,series_id:sid,revision,
               candidate_id:payload.candidate_id,pair:payload.pair,
               phase:payload.phase,result:payload.result,
               source_known_at:payload.known_at_utc,payload,
               content_sha256:rec.sha256};
    const {error}=await db.from("v3_paper_event_receipts").insert(row);
    if(error){
      if(error.code!=="23505")return respond(500,{ok:false,error:"append_failed"});
      const {data:old,error:lookup}=await db.from("v3_paper_event_receipts")
        .select("content_sha256").eq("event_id",rec.event_id).maybeSingle();
      if(lookup||old?.content_sha256!==rec.sha256)
        return respond(409,{ok:false,error:"historical_receipt_collision"});
    }
    accepted++;
  }
  return respond(200,{ok:true,accepted_receipts:accepted,
    series_id:sid,paper_only:true,immutable:true,orders:false,real_money_actions:false});
});
