// INACTIVE DRAFT. Deploy only after the SQL migration, physical cutover script
// and mandatory release review are verified. Separate from the first-series relay.
// No order API, no candidate evaluation and no H3 baseline migration.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const OLD="PAPER-V2R4-20261007T184255Z";
const OLD_SHA="3c6729a6c548d169f56a97f07f75892f37211636";
const STAGED_SHA="927e8c8d4455c28bb0cb230e86eb1d83bc09576f";
const CONFIRM="CUTOVER_V2R4_TECHNICAL_PAPER_ONLY";
const REV="V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION";
const headers={"Content-Type":"application/json","Cache-Control":"no-store"};
function send(status:number,body:Record<string,unknown>){
  return new Response(JSON.stringify(body),{status,headers});
}
function hexMatch(a:string,b:string){
  if(a.length!==64||b.length!==64)return false;
  let diff=0;for(let i=0;i<a.length;i++)diff|=a.charCodeAt(i)^b.charCodeAt(i);
  return diff===0;
}
async function credential(admin:any,token:string,relayId:string){
  if(token.length<24)return false;
  const {data,error}=await admin.from("internal_relay_credentials")
    .select("token_sha256,enabled").eq("relay_id",relayId).maybeSingle();
  if(error||data?.enabled!==true||typeof data?.token_sha256!=="string")return false;
  const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(token));
  const hash=Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,"0")).join("");
  return hexMatch(hash,data.token_sha256);
}
function safeHex(value:unknown,n:number){
  return typeof value==="string"&&new RegExp("^[0-9a-f]{"+n+"}$").test(value);
}
async function sourceGate(admin:any){
  const {data,error}=await admin.from("minipc_status_current")
    .select("observed_at,status,payload").limit(1).maybeSingle();
  if(error||!data)return {ok:false,code:"status_missing"};
  const age=Date.now()-Date.parse(data.observed_at);
  if(!Number.isFinite(age)||age<0||age>180000)return {ok:false,code:"status_stale"};
  const c=data.payload?.checks||{};
  // Deliberately do NOT demand old PaperCandidates=HEALTHY here: that runtime
  // is the known frozen alias bug we are replacing. Independent market and
  // supervisor processes MUST be healthy; no generic warning bypass.
  const required=["kraken_universe_heartbeat","kraken_canary_heartbeat",
    "v2r4_ws_shadow_heartbeat","runtime_supervisor","v2r4_paper_cloud_sync"];
  const bad=required.filter(key=>c[key]?.ok!==true);
  if(bad.length)return {ok:false,code:"source_or_supervisor_unhealthy",failed:bad};
  if(c.git_head?.ok!==true||String(c.git_head?.detail??"").includes(STAGED_SHA)!==true)
    return {ok:false,code:"unexpected_repo_head"};
  return {ok:true,code:"SOURCE_GATE_PASS"};
}
Deno.serve(async(req:Request)=>{
  if(req.method!=="POST")return send(405,{ok:false,error:"method_not_allowed"});
  if(Number(req.headers.get("content-length")??0)>16384)
    return send(413,{ok:false,error:"oversized_request"});
  const supabaseUrl=Deno.env.get("SUPABASE_URL")??"";
  const serviceKey=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")??"";
  if(!supabaseUrl||!serviceKey)return send(503,{ok:false,error:"service_unavailable"});
  const admin=createClient(supabaseUrl,serviceKey,{auth:{persistSession:false,autoRefreshToken:false}});
  const paperToken=req.headers.get("X-Shadow-Evidence-Token")??"";
  const statusToken=req.headers.get("X-MiniPC-Status-Token")??"";
  if(!(await credential(admin,paperToken,"v2r4-shadow-evidence-relay"))||
     !(await credential(admin,statusToken,"minipc-status-relay")))
    return send(401,{ok:false,error:"dual_authorization_failed"});
  let body:any;
  try { body=await req.json(); } catch { return send(400,{ok:false,error:"invalid_json"}); }
  if(body?.action==="readiness"){
    const health=await sourceGate(admin);
    const {data:old}=await admin.from("paper_series")
      .select("series_id,status").eq("series_id",OLD).maybeSingle();
    return send(200,{ok:true,action:"readiness",source_gate:health,
      old_series_status:old?.status??"missing",mutation:false});
  }
  if(body?.action!=="cutover")return send(400,{ok:false,error:"unsupported_action"});
  if(req.headers.get("X-Cutover-Confirm")!==CONFIRM)
    return send(403,{ok:false,error:"cutover_not_confirmed"});

  const m=body?.manifest;
  if(!m||typeof m!=="object"||Array.isArray(m))
    return send(400,{ok:false,error:"manifest_missing"});
  const config=m.new_config;
  const proof=m.physical_proof;
  if(m.old_series_id!==OLD||m.expected_old_release_sha!==OLD_SHA||
     m.new_series_id!==config?.series_id||
     m.new_test_id!==config?.test_id||
     config?.strategy_revision!==REV||
     config?.release_repo_sha!==STAGED_SHA||
     !safeHex(config?.runtime_bundle_fingerprint_sha256,64)||
     !safeHex(config?.strategy_fingerprint_sha256,64)||
     config?.paper_only!==true||config?.real_money_actions_enabled!==false||
     config?.automatic_activation_allowed!==false||
     config?.technical_change_approved!==true||
     !Number.isSafeInteger(m.expected_old_outcomes)||
     !Number.isSafeInteger(m.expected_old_trades)||
     m.expected_old_outcomes<0||m.expected_old_trades<0||
     typeof m.cutover_at_utc!=="string"||
     typeof m.expected_old_last_updated_at!=="string"||
     typeof proof!=="object"||
     proof?.old_paper_tasks_stopped!==true||proof?.h3_001_stopped!==true||
     proof?.last_old_sync_acknowledged!==true||
     proof?.snapshot_verified!==true||
     proof?.staged_app_still_inert!==true||
     proof?.orders_disabled!==true||
     !safeHex(proof?.snapshot_sha256,64)||
     !safeHex(proof?.staged_manifest_sha256,64))
    return send(409,{ok:false,error:"manifest_or_physical_proof_incomplete"});
  // Physical proofs must come from the dedicated, hash-verifying Mini-PC
  // operator script; this endpoint cannot independently read its filesystem.
  const gate=await sourceGate(admin);
  if(!gate.ok)return send(409,{ok:false,error:"source_gate_blocked",details:gate});
  const {data:prior,error:priorErr}=await admin.from("paper_technical_rotations")
    .select("predecessor_series_id,successor_series_id").eq("predecessor_series_id",OLD).maybeSingle();
  // Only the already-applied schema is accepted. Fail closed if missing.
  if(priorErr)return send(409,{ok:false,error:"rotation_schema_missing_or_unreadable"});
  if(prior && prior.successor_series_id!==m.new_series_id)
    return send(409,{ok:false,error:"conflicting_previous_rotation"});
  try{
    const {data,error}=await admin.rpc("rotate_v2r4_technical_paper",{
      p_old_series_id:m.old_series_id,
      p_new_series_id:m.new_series_id,
      p_new_test_id:m.new_test_id,
      p_cutover_at_utc:m.cutover_at_utc,
      p_new_config:config,
      p_expected_old_release_sha:m.expected_old_release_sha,
      p_expected_old_outcomes:m.expected_old_outcomes,
      p_expected_old_trades:m.expected_old_trades,
      p_expected_old_last_updated_at:m.expected_old_last_updated_at
    });
    if(error||data?.ok!==true)return send(409,{ok:false,error:"atomic_rotation_rejected"});
    return send(200,{ok:true,action:"cutover",
      predecessor_series_id:OLD,successor_series_id:m.new_series_id,
      idempotent:data.idempotent===true,orders:false,real_money_actions:false});
  }catch{return send(503,{ok:false,error:"rotation_result_unknown_read_back_before_retry"});}
});
