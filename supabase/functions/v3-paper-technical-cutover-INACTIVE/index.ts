// INACTIVE SOURCE ONLY: separately privileged V3 Paper CAS owner preflight.
// Not deployed; no mutate/GRANT/RPC/Task/strategy activation. An exact
// read-only checkpoint does NOT authenticate the physical Mini-PC or grant CAS.
import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {createClient} from "npm:@supabase/supabase-js@2";
const FIRST_ID="v3-paper-cutover-preflight-primary";
const SECOND_ID="v3-paper-cutover-preflight-independent";
const HEX=/^[0-9a-f]{64}$/;
const OLD=/^PAPER-V2R4-[0-9]{8}T[0-9]{6}Z$/;
const headers={"Content-Type":"application/json","Cache-Control":"no-store"};
function send(status:number,obj:Record<string,unknown>){
 return new Response(JSON.stringify(obj),{status,headers});
}
async function keyValid(db:any,key:string,role:string){
 if(key.length<32||key.length>512||/\s/.test(key))return false;
 const {data,error}=await db.from("internal_relay_credentials")
   .select("token_sha256,enabled").eq("relay_id",role).maybeSingle();
 if(error||data?.enabled!==true||typeof data.token_sha256!=="string"||
    !HEX.test(data.token_sha256))return false;
 const bytes=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(key));
 const digest=Array.from(new Uint8Array(bytes))
   .map(x=>x.toString(16).padStart(2,"0")).join("");
 let mismatch=0;
 for(let i=0;i<64;i++)mismatch|=digest.charCodeAt(i)^data.token_sha256.charCodeAt(i);
 return mismatch===0;
}
async function version(db:any,table:string,id:string){
 // Preview only: count and last update are two SELECTs, not a CAS lock.
 const {count,error}=await db.from(table).select("candidate_id",{
   count:"exact",head:true}).eq("series_id",id);
 if(error||typeof count!=="number"||!Number.isSafeInteger(count)||count<0)
   throw new Error("candidate_or_trade_count_unavailable");
 const {data,error:err}=await db.from(table).select("updated_at")
   .eq("series_id",id).order("updated_at",{
      ascending:false,nullsFirst:false}).limit(1);
 if(err||!Array.isArray(data))throw new Error("last_version_unavailable");
 const updated=data.length?data[0].updated_at:null;
 if(count===0?updated!==null:typeof updated!=="string"||
     !Number.isFinite(Date.parse(updated)))
   throw new Error("count_version_mismatch");
 return {count,updated};
}
Deno.serve(async(request:Request)=>{
 if(request.method!=="POST")return send(405,{ok:false,error:"method_not_allowed"});
 if(Deno.env.get("V3_PAPER_PRECAS_CHECKPOINT_ENABLED")!=="READONLY_APPROVED")
   return send(503,{ok:false,error:"preflight_not_enabled"});
 const url=Deno.env.get("SUPABASE_URL")??"";
 const key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")??"";
 if(!url||!key)return send(503,{ok:false,error:"server_unavailable"});
 if(Number(request.headers.get("content-length")??0)>2048)
   return send(413,{ok:false,error:"oversized"});
 const first=request.headers.get("X-V3-Paper-Cutover-Preflight-Token")??"";
 const second=request.headers.get("X-V3-Paper-Independent-Preflight-Token")??"";
 if(!first||!second||first===second)return send(401,{ok:false,error:"distinct_preflight_credentials_required"});
 const db=createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false}});
 if(!await keyValid(db,first,FIRST_ID)||!await keyValid(db,second,SECOND_ID))
   return send(401,{ok:false,error:"preflight_authentication_failed"});
 let body:any;
 try{body=await request.json();}catch{return send(400,{ok:false,error:"invalid_json"});}
 if(!body||typeof body!=="object"||Array.isArray(body)||
   body.action!=="checkpoint"||typeof body.predecessor_series_id!=="string"||
   !OLD.test(body.predecessor_series_id)||Object.keys(body).length!==2)
   return send(400,{ok:false,error:"only_exact_readonly_checkpoint_supported"});
 try{
   const id=body.predecessor_series_id;
   const {data,error}=await db.from("paper_series")
     .select("series_id,status,strategy_revision,config")
     .eq("status","active").limit(2);
   if(error||!Array.isArray(data)||data.length!==1||
      data[0].series_id!==id||!String(data[0].strategy_revision).startsWith("V2R4-"))
      return send(409,{ok:false,error:"wrong_active_predecessor"});
   const c=data[0].config;
   if(!c||typeof c!=="object"||c.paper_only!==true||
      c.real_money_actions_enabled!==false||
      c.automatic_activation_allowed!==false||
      typeof c.release_repo_sha!=="string"||
      !/^[0-9a-f]{40}$/.test(c.release_repo_sha)||
      !HEX.test(c.runtime_bundle_fingerprint_sha256)||
      !HEX.test(c.strategy_fingerprint_sha256))
      return send(409,{ok:false,error:"unsafe_or_unpinned_predecessor"});
   const candidates=await version(db,"paper_candidate_outcomes",id);
   const trades=await version(db,"paper_trade_results",id);
   // The future privileged SQL CAS MUST re-read BOTH counts AND versions
   // under a DB transaction lock. No preflight authorizes execution/retry.
   return send(200,{
     ok:true,kind:"V3_PRECAS_CLOUD_ORIGINAL_SNAPSHOT_READONLY_V1",
     predecessor_series_id:id,phase:"CAS_NOT_ATTEMPTED",
     observed_at_utc:new Date().toISOString(),
     expected_old_release_sha:c.release_repo_sha,
     expected_old_runtime_sha256:c.runtime_bundle_fingerprint_sha256,
     expected_old_strategy_sha256:c.strategy_fingerprint_sha256,
     original_candidate_count:candidates.count,
     original_last_candidate_updated_at:candidates.updated,
     original_trade_count:trades.count,
     original_last_trade_updated_at:trades.updated,
     read_only:true,cloud_mutations:false,cloud_cas_invoked:false,
     physical_originalhost_verified:false,six_release_proofs_credited:0,
     cas_execution_authorized:false,safe_to_retry_unknown_cas:false
   });
 }catch{return send(503,{ok:false,error:"checkpoint_failed_no_execution"});}
});
