import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

const jsonHeaders={"Content-Type":"application/json"};
function response(status:number,body:Record<string,unknown>){return new Response(JSON.stringify(body),{status,headers:jsonHeaders});}
function sameFixedHex(a:string,b:string){if(a.length!==64||b.length!==64)return false;let d=0;for(let i=0;i<64;i++)d|=a.charCodeAt(i)^b.charCodeAt(i);return d===0;}
async function credentialAuthorized(admin:any,supplied:string,relayId:string){
  const {data:cred,error}=await admin.from("internal_relay_credentials")
    .select("token_sha256,enabled").eq("relay_id",relayId).maybeSingle();
  if(error||cred?.enabled!==true||typeof cred.token_sha256!=="string"||!supplied)return false;
  const digest=await crypto.subtle.digest("SHA-256",new TextEncoder().encode(supplied));
  const hash=Array.from(new Uint8Array(digest)).map(b=>b.toString(16).padStart(2,"0")).join("");
  return sameFixedHex(hash,cred.token_sha256);
}
async function authorized(admin:any,req:Request){
  return credentialAuthorized(admin,req.headers.get("X-Shadow-Evidence-Token")??"","v2r4-shadow-evidence-relay");
}
function latestIso(values:any[],fallback:string){
  let bestMs=Number.NEGATIVE_INFINITY;
  let best=fallback;
  for(const value of values){
    if(typeof value!=="string"||!value)continue;
    const ms=new Date(value).getTime();
    if(!Number.isNaN(ms)&&ms>bestMs){bestMs=ms;best=new Date(ms).toISOString();}
  }
  return best;
}
function candidateUpdatedAt(row:any){
  return latestIso([
    row?.evaluated_at,
    row?.payload?.decision?.evaluated_at_utc,
    row?.payload?.recheck?.recheck_completed_at_utc,
    row?.payload?.recheck?.completed_at_utc,
    row?.payload?.recheck?.revalidated_at_utc,
    row?.payload?.followup?.updated_at_utc,
    row?.payload?.followup?.opportunity_audit?.updated_at_utc,
  ],String(row?.evaluated_at??new Date(0).toISOString()));
}
function tradeUpdatedAt(row:any){
  const events=Array.isArray(row?.payload?.events)?row.payload.events:[];
  return latestIso([
    row?.opened_at,row?.closed_at,row?.payload?.updated_at_utc,
    row?.payload?.exit?.closed_at_utc,...events.map((x:any)=>x?.at_utc),
  ],String(row?.opened_at??new Date(0).toISOString()));
}

Deno.serve(async(req:Request)=>{
  if(req.method!=="POST")return response(405,{ok:false,error:"method_not_allowed"});
  const url=Deno.env.get("SUPABASE_URL")??""; const key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")??"";
  if(!url||!key)return response(500,{ok:false,error:"server_credentials_missing"});
  const admin=createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false}});
  if(!(await authorized(admin,req)))return response(401,{ok:false,error:"unauthorized"});
  let body:any; try{body=await req.json();}catch{return response(400,{ok:false,error:"invalid_json"});}
  const action=String(body?.action??"");

  if(action==="activate"){
    const statusToken=req.headers.get("X-MiniPC-Status-Token")??"";
    if(!(await credentialAuthorized(admin,statusToken,"minipc-status-relay")))
      return response(401,{ok:false,error:"activation_second_factor_unauthorized"});

    const {data:minipc,error:minipcErr}=await admin.from("minipc_status_current")
      .select("observed_at,status,payload").order("observed_at",{ascending:false}).limit(1).maybeSingle();
    if(minipcErr||!minipc)return response(409,{ok:false,error:"minipc_health_unavailable"});
    const minipcAgeMs=Date.now()-new Date(minipc.observed_at).getTime();
    if(Number.isNaN(minipcAgeMs)||minipcAgeMs<0||minipcAgeMs>5*60*1000||
       minipc.status!=="HEALTHY"||minipc.payload?.health_state!=="OK")
      return response(409,{ok:false,error:"minipc_not_fresh_healthy_ok"});

    const seriesId=String(body?.series_id??""); const testId=String(body?.test_id??""); const revision=String(body?.strategy_revision??""); const startedAt=String(body?.started_at??""); const config=body?.config;
    if(!/^PAPER-V2R4-\d{8}T\d{6}Z$/.test(seriesId))return response(400,{ok:false,error:"invalid_series_id"});
    if(!/^PAPER-V2R4-SERIES1-\d{8}$/.test(testId))return response(400,{ok:false,error:"invalid_test_id"});
    if(revision!=="V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION")return response(400,{ok:false,error:"invalid_strategy_revision"});
    const dt=new Date(startedAt); if(Number.isNaN(dt.getTime()))return response(400,{ok:false,error:"invalid_started_at"});
    if(!config||typeof config!=="object"||config.paper_only!==true||config.real_money_actions_enabled!==false||config.enabled!==true)return response(400,{ok:false,error:"unsafe_config"});
    if(config.series_id!==seriesId||config.test_id!==testId||config.strategy_revision!==revision)return response(400,{ok:false,error:"config_identity_mismatch"});
    if(Number(config.target_completed_paper_trades)!==20)return response(400,{ok:false,error:"unexpected_target"});
    if(config.release_decision!=="APPROVED_PAPER"||config.automatic_activation_allowed!==false)return response(400,{ok:false,error:"invalid_release_control"});
    if(Number(config.scout_notional_eur)!==50||Number(config.stage2_notional_eur)!==50)return response(400,{ok:false,error:"unexpected_first_series_sizing"});
    const releaseRepoSha=String(config.release_repo_sha??"").toLowerCase();
    const candidateMergeSha=String(config.candidate_merge_sha??"").toLowerCase();
    const strategyFingerprint=String(config.strategy_fingerprint_sha256??"").toLowerCase();
    const runtimeFingerprint=String(config.runtime_bundle_fingerprint_sha256??"").toLowerCase();
    if(!/^[a-f0-9]{40}$/.test(releaseRepoSha)||!/^[a-f0-9]{40}$/.test(candidateMergeSha))return response(400,{ok:false,error:"invalid_release_sha_provenance"});
    if(!/^[a-f0-9]{64}$/.test(strategyFingerprint)||!/^[a-f0-9]{64}$/.test(runtimeFingerprint))return response(400,{ok:false,error:"invalid_fingerprint_provenance"});

    const {data:release,error:relErr}=await admin.from("strategy_release_decisions").select("status,predecessor_series_id,successor_revision,final_review_completed_at,migration_review_completed_at,decision_evidence").eq("release_id","V2R3_TO_V2R4_20261005").maybeSingle();
    if(relErr||!release)return response(500,{ok:false,error:"release_lookup_failed"});
    const releaseEvidence=release.decision_evidence??{};
    if(
      release.status!=="APPROVED_PAPER"||
      release.predecessor_series_id!=="PAPER-V2R3-CLEAN-20261001T0925Z"||
      release.successor_revision!=="V2R4"||
      !release.final_review_completed_at||!release.migration_review_completed_at||
      releaseEvidence.explicit_user_release_decision!=="APPROVED_PAPER"||
      releaseEvidence.minipc_release_gate?.status!=="PASS"||
      releaseEvidence.real_altrady_release_smoke?.status!=="PASS"||
      releaseEvidence.real_money_actions_allowed!==false
    )return response(409,{ok:false,error:"release_not_approved"});
    const recordedSeries=releaseEvidence.activation_series_id;
    if(recordedSeries && recordedSeries!==seriesId)return response(409,{ok:false,error:"different_activation_already_recorded",series_id:recordedSeries});

    const {data:existing,error:exErr}=await admin.from("paper_series").select("series_id,status,strategy_revision").eq("series_id",seriesId).maybeSingle();
    if(exErr)return response(500,{ok:false,error:"series_lookup_failed"});
    if(existing && (existing.status!=="active"||existing.strategy_revision!==revision))return response(409,{ok:false,error:"series_identity_conflict"});

    let freshActivation=false;
    if(!existing){
      // Fail closed at the strategy boundary: retire the completed predecessor
      // before inserting the successor, so two active paper series can never
      // coexist. On any subsequent failure, compensate back to the predecessor.
      const {data:closed,error:closeErr}=await admin.from("paper_series")
        .update({status:"closed_complete",updated_at:new Date().toISOString()})
        .eq("series_id","PAPER-V2R3-CLEAN-20261001T0925Z").eq("status","active")
        .select("series_id");
      if(closeErr)return response(500,{ok:false,error:"predecessor_close_failed",detail:closeErr.message});
      if(!closed || closed.length!==1)return response(409,{ok:false,error:"predecessor_not_active_without_successor"});

      const {error:insErr}=await admin.from("paper_series").insert({
        series_id:seriesId,test_id:testId,strategy_revision:revision,started_at:dt.toISOString(),
        target_completed_trades:20,status:"active",config
      });
      if(insErr){
        await admin.from("paper_series")
          .update({status:"active",updated_at:new Date().toISOString()})
          .eq("series_id","PAPER-V2R3-CLEAN-20261001T0925Z").eq("status","closed_complete");
        return response(500,{ok:false,error:"series_insert_failed",detail:insErr.message});
      }
      freshActivation=true;
    } else {
      // Idempotent retry after a server-success/client-timeout: ensure the old
      // completed series is not still marked active.
      const {error:closeErr}=await admin.from("paper_series")
        .update({status:"closed_complete",updated_at:new Date().toISOString()})
        .eq("series_id","PAPER-V2R3-CLEAN-20261001T0925Z").eq("status","active");
      if(closeErr)return response(500,{ok:false,error:"predecessor_close_failed",detail:closeErr.message});
    }

    if(!recordedSeries){
      const evidence={
        ...(release.decision_evidence??{}),
        activation_series_id:seriesId,
        activation_test_id:testId,
        activation_started_at:dt.toISOString(),
        activation_runtime_owner:"MINIPC_LOCAL_V2R4",
        activation_recorded_at:new Date().toISOString(),
        activation_release_repo_sha:releaseRepoSha,
        activation_candidate_merge_sha:candidateMergeSha,
        activation_strategy_fingerprint_sha256:strategyFingerprint,
        activation_runtime_bundle_fingerprint_sha256:runtimeFingerprint,
        real_money_actions_allowed:false
      };
      const {error:updErr}=await admin.from("strategy_release_decisions")
        .update({decision_evidence:evidence,updated_at:new Date().toISOString()})
        .eq("release_id","V2R3_TO_V2R4_20261005");
      if(updErr){
        if(freshActivation){
          await admin.from("paper_series").delete().eq("series_id",seriesId);
          await admin.from("paper_series")
            .update({status:"active",updated_at:new Date().toISOString()})
            .eq("series_id","PAPER-V2R3-CLEAN-20261001T0925Z").eq("status","closed_complete");
        }
        return response(500,{ok:false,error:"release_evidence_update_failed"});
      }
    }
    return response(200,{
      ok:true,action:"activate",series_id:seriesId,status:"active",idempotent:Boolean(recordedSeries),
      release_repo_sha:releaseRepoSha,strategy_fingerprint_sha256:strategyFingerprint,
      runtime_bundle_fingerprint_sha256:runtimeFingerprint,paper_only:true,real_money_actions:false
    });
  }

  if(action==="sync"){
    const seriesId=String(body?.series_id??""); const revision=String(body?.strategy_revision??""); const candidates=body?.candidates; const trades=body?.trades;
    if(!/^PAPER-V2R4-\d{8}T\d{6}Z$/.test(seriesId))return response(400,{ok:false,error:"invalid_series_id"});
    if(revision!=="V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION")return response(400,{ok:false,error:"invalid_strategy_revision"});
    if(!Array.isArray(candidates)||candidates.length>500||!Array.isArray(trades)||trades.length>100)return response(400,{ok:false,error:"invalid_batch"});
    const {data:series,error:sErr}=await admin.from("paper_series").select("series_id,status,strategy_revision").eq("series_id",seriesId).maybeSingle();
    if(sErr||!series)return response(409,{ok:false,error:"series_not_found"});
    if(series.status!=="active"||series.strategy_revision!==revision)return response(409,{ok:false,error:"series_not_active"});
    for(const row of candidates){
      if(row?.series_id!==seriesId||typeof row?.candidate_id!=="string"||typeof row?.pair!=="string"||row?.payload?.decision?.real_money_actions_enabled!==false)
        return response(400,{ok:false,error:"unsafe_candidate_payload"});
      if(!["BUY_SCOUT","WAIT","REJECT"].includes(String(row?.decision??"")))
        return response(400,{ok:false,error:"invalid_candidate_decision"});
      const recheck=row?.payload?.recheck;
      if(recheck!=null && (recheck.paper_only!==true||recheck.real_money_actions_enabled!==false||recheck.order_api!==false))
        return response(400,{ok:false,error:"unsafe_recheck_payload"});
    }
    for(const row of trades){
      if(row?.series_id!==seriesId||typeof row?.candidate_id!=="string"||row?.payload?.real_money_actions_enabled!==false)
        return response(400,{ok:false,error:"unsafe_trade_payload"});
    }
    if(candidates.length){
      const rows=candidates.map((row:any)=>({...row,updated_at:candidateUpdatedAt(row)}));
      const {error}=await admin.from("paper_candidate_outcomes").upsert(rows,{onConflict:"candidate_id"});
      if(error)return response(500,{ok:false,error:"candidate_upsert_failed",detail:error.message});
    }
    if(trades.length){
      const rows=trades.map((row:any)=>({...row,updated_at:tradeUpdatedAt(row)}));
      const {error}=await admin.from("paper_trade_results").upsert(rows,{onConflict:"candidate_id"});
      if(error)return response(500,{ok:false,error:"trade_upsert_failed",detail:error.message});
    }
    return response(200,{ok:true,action:"sync",accepted_candidates:candidates.length,accepted_trades:trades.length,paper_only:true,real_money_actions:false});
  }

  if(action==="sync_h3_shadow"){
    const shadowId=String(body?.shadow_candidate_id??"");
    const seriesId=String(body?.baseline_series_id??"");
    const revision=String(body?.baseline_strategy_revision??"");
    const evidence=body?.evidence;
    const status=body?.status;
    if(shadowId!=="V3-H3-SHADOW-001")return response(400,{ok:false,error:"invalid_h3_shadow_id"});
    if(seriesId!=="PAPER-V2R4-20261007T184255Z")return response(400,{ok:false,error:"invalid_h3_baseline_series"});
    if(revision!=="V2R4-RELEASE-CANDIDATE-2026-10-05-TIMING-ISOLATION")return response(400,{ok:false,error:"invalid_h3_baseline_revision"});
    if(!Array.isArray(evidence)||evidence.length>100||!status||typeof status!=="object")
      return response(400,{ok:false,error:"invalid_h3_batch"});

    const {data:series,error:sErr}=await admin.from("paper_series")
      .select("series_id,status,strategy_revision").eq("series_id",seriesId).maybeSingle();
    if(sErr||!series)return response(409,{ok:false,error:"h3_baseline_series_not_found"});
    if(series.status!=="active"||series.strategy_revision!==revision)
      return response(409,{ok:false,error:"h3_baseline_series_not_active"});

    const allowedPairs=new Set(["XBT/EUR","ETH/EUR","SOL/EUR"]);
    const allowedDecisions=new Set(["BUY_SCOUT","WAIT","REJECT"]);
    for(const row of evidence){
      if(row?.shadow_candidate_id!==shadowId||row?.baseline_series_id!==seriesId||
         typeof row?.candidate_id!=="string"||!allowedPairs.has(String(row?.pair??"")))
        return response(400,{ok:false,error:"invalid_h3_evidence_identity"});
      if(!["PASS","MISSING_FAIL_CLOSED"].includes(String(row?.context_status??"")))
        return response(400,{ok:false,error:"invalid_h3_context_status"});
      for(const field of ["baseline_decision","control_replay_decision","shadow_decision"]){
        if(!allowedDecisions.has(String(row?.[field]??"")))
          return response(400,{ok:false,error:"invalid_h3_decision_field",field});
      }
      const g=row?.payload?.guardrails;
      if(!g||g.orders!==false||g.real_money_actions!==false||g.automatic_promotion!==false)
        return response(400,{ok:false,error:"unsafe_h3_evidence_payload"});
      if(row?.decision_diverged!==true&&row?.decision_diverged!==false)
        return response(400,{ok:false,error:"invalid_h3_divergence_flag"});
      if(row?.baseline_replay_stable!==true&&row?.baseline_replay_stable!==false)
        return response(400,{ok:false,error:"invalid_h3_replay_stability_flag"});
    }
    const sg=status?.payload?.guardrails;
    if(status.shadow_candidate_id!==shadowId||typeof status.generated_at!=="string"||
       !status.payload||status.payload.shadow_candidate_id!==shadowId||
       status.payload.baseline_series_id!==seriesId||
       status.payload.orders!==false||status.payload.real_money_actions!==false||
       status.payload.automatic_promotion!==false)
      return response(400,{ok:false,error:"unsafe_h3_status_payload"});

    if(evidence.length){
      const rows=evidence.map((row:any)=>({
        ...row,
        updated_at:latestIso(
          [row?.payload?.baseline_evaluated_at_utc,row?.candidate_event_time],
          String(row?.candidate_event_time??new Date(0).toISOString()),
        ),
      }));
      const {error}=await admin.from("v3_h3_shadow_evidence").upsert(rows,{onConflict:"candidate_id"});
      if(error)return response(500,{ok:false,error:"h3_evidence_upsert_failed",detail:error.message});
    }
    const statusRow={...status,updated_at:new Date(status.generated_at).toISOString()};
    const {error:stErr}=await admin.from("v3_h3_shadow_status").upsert(statusRow,{onConflict:"shadow_candidate_id"});
    if(stErr)return response(500,{ok:false,error:"h3_status_upsert_failed",detail:stErr.message});
    return response(200,{
      ok:true,action:"sync_h3_shadow",accepted_evidence:evidence.length,
      shadow_candidate_id:shadowId,baseline_series_id:seriesId,
      orders:false,real_money_actions:false,automatic_promotion:false
    });
  }

  return response(400,{ok:false,error:"unsupported_action"});
});
