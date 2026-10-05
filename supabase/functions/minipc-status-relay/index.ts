import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const jsonHeaders={"Content-Type":"application/json"};
const MAX_FUTURE_MS=2*60*1000;
const MAX_STATUS_AGE_MS=15*60*1000;

function response(status:number,body:Record<string,unknown>){
  return new Response(JSON.stringify(body),{status,headers:jsonHeaders});
}

Deno.serve(async(req:Request)=>{
  if(req.method!=="POST") return response(405,{ok:false,error:"method_not_allowed"});

  const url=Deno.env.get("SUPABASE_URL") ?? "";
  const serviceKey=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  if(!url || !serviceKey) return response(500,{ok:false,error:"server_credentials_missing"});
  const admin=createClient(url,serviceKey,{auth:{persistSession:false,autoRefreshToken:false}});

  const supplied=req.headers.get("X-MiniPC-Status-Token") ?? "";
  const {data:cred,error:credError}=await admin.from("internal_relay_credentials")
    .select("token_sha256,enabled").eq("relay_id","minipc-status-relay").maybeSingle();
  if(credError) return response(500,{ok:false,error:"credential_lookup_failed"});
  let authorized=false;
  if(cred?.enabled===true){
    const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(supplied));
    const hash=Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,"0")).join("");
    authorized=hash===cred.token_sha256;
  }else{
    const legacy=Deno.env.get("MINIPC_STATUS_TOKEN") ?? Deno.env.get("ALTRADY_WEBHOOK_TOKEN") ?? "";
    authorized=Boolean(legacy) && supplied===legacy;
  }
  if(!authorized) return response(401,{ok:false,error:"unauthorized"});

  let body:any;
  try{body=await req.json();}catch{return response(400,{ok:false,error:"invalid_json"});}

  const nodeId=typeof body?.node_id==="string"?body.node_id.trim():"";
  const observedAt=typeof body?.observed_at==="string"?body.observed_at.trim():"";
  const status=typeof body?.status==="string"?body.status.trim().toUpperCase():"";
  const payload=body?.payload;

  if(!/^[A-Za-z0-9._-]{1,64}$/.test(nodeId)) return response(400,{ok:false,error:"invalid_node_id"});
  if(!["HEALTHY","WARNING","CRITICAL","UNKNOWN"].includes(status)) return response(400,{ok:false,error:"invalid_status"});
  const dt=new Date(observedAt);
  if(!observedAt || Number.isNaN(dt.getTime())) return response(400,{ok:false,error:"invalid_observed_at"});
  const nowMs=Date.now();
  const age=nowMs-dt.getTime();
  if(age < -MAX_FUTURE_MS) return response(400,{ok:false,error:"observed_at_too_far_future"});
  if(age > MAX_STATUS_AGE_MS) return response(409,{ok:false,error:"stale_status_rejected"});
  if(!payload || typeof payload!=="object" || Array.isArray(payload)) return response(400,{ok:false,error:"invalid_payload"});
  if(payload.kind!=="MINIPC_LOCAL_HEALTH_V1") return response(400,{ok:false,error:"invalid_payload_kind"});
  if(String(payload.computer_name ?? "")!==nodeId) return response(400,{ok:false,error:"payload_node_mismatch"});
  if(String(payload.status ?? "UNKNOWN").toUpperCase()!==status) return response(400,{ok:false,error:"payload_status_mismatch"});
  const payloadTime=new Date(String(payload.checked_at_local ?? ""));
  if(Number.isNaN(payloadTime.getTime()) || Math.abs(payloadTime.getTime()-dt.getTime())>90*1000){
    return response(400,{ok:false,error:"payload_timestamp_mismatch"});
  }

  const {data:existing,error:readError}=await admin.from("minipc_status_current")
    .select("node_id,observed_at").eq("node_id",nodeId).maybeSingle();
  if(readError) return response(500,{ok:false,error:"existing_status_lookup_failed"});
  if(existing?.observed_at){
    const prev=new Date(existing.observed_at).getTime();
    if(dt.getTime()<prev) return response(409,{ok:false,error:"out_of_order_status_rejected"});
    if(dt.getTime()===prev) return response(200,{ok:true,node_id:nodeId,status,idempotent:true});
  }

  const row={node_id:nodeId,observed_at:dt.toISOString(),status,payload,updated_at:new Date().toISOString()};
  const {error}=await admin.from("minipc_status_current").upsert(row,{onConflict:"node_id"});
  if(error){
    console.error("minipc status upsert failed",error.message);
    return response(500,{ok:false,error:"upsert_failed"});
  }
  return response(200,{ok:true,node_id:nodeId,status,idempotent:false});
});