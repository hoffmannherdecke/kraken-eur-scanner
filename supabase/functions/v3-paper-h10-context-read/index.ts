import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import {createClient} from "npm:@supabase/supabase-js@2";

// Only the EXISTING H10 30m Cloud capture is read. No source polling,
// wallet/private keys, user orders, source promotion or strategy activation.
const RELAY_ID="v3-paper-evidence-relay";
const HEX=/^[0-9a-f]{64}$/;
const PAIR=/^[A-Z0-9]{2,12}\/EUR$/;
function respond(status:number,body:Record<string,unknown>){
  return new Response(JSON.stringify(body),{status,headers:{
    "Content-Type":"application/json","Cache-Control":"no-store",
    "X-Content-Type-Options":"nosniff"
  }});
}
function asHex(d:ArrayBuffer){
  return Array.from(new Uint8Array(d)).map(x=>x.toString(16).padStart(2,"0")).join("");
}
async function authorized(db:any,req:Request):Promise<boolean>{
  const supplied=req.headers.get("X-V3-Paper-Evidence-Token")??"";
  if(supplied.length<24||supplied.length>512)return false;
  const {data,error}=await db.from("internal_relay_credentials")
    .select("token_sha256,enabled").eq("relay_id",RELAY_ID).maybeSingle();
  if(error||data?.enabled!==true||!HEX.test(data.token_sha256))return false;
  const hashed=asHex(await crypto.subtle.digest("SHA-256",
    new TextEncoder().encode(supplied)));
  let mismatch=0;
  for(let i=0;i<64;i++)mismatch|=hashed.charCodeAt(i)^data.token_sha256.charCodeAt(i);
  return mismatch===0;
}
Deno.serve(async(req:Request)=>{
  if(req.method!=="POST")return respond(405,{ok:false,error:"method_not_allowed"});
  if(Number(req.headers.get("content-length")??0)>4096)
    return respond(413,{ok:false,error:"oversized"});
  const url=Deno.env.get("SUPABASE_URL")??"";
  const key=Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")??"";
  if(!url||!key)return respond(503,{ok:false,error:"server_config_missing"});
  const db=createClient(url,key,{auth:{persistSession:false,autoRefreshToken:false}});
  if(!await authorized(db,req))return respond(401,{ok:false,error:"unauthorized"});
  let input:any;
  try{input=await req.json();}catch{return respond(400,{ok:false,error:"invalid_json"});}
  const pair=input?.pair;
  if(input?.action!=="read_existing_h10_optional_context"||
     typeof pair!=="string"||!PAIR.test(pair))
    return respond(400,{ok:false,error:"only_one_public_kraken_eur_pair_allowed"});
  const coin=pair==="XBT/EUR"?"BTC":pair.slice(0,-4);
  // Source is the already existing PRIMARY cohort research collector.
  // LAST ACTIVITY, never now(), controls freshness; no retroactive reweight.
  const {data,error}=await db.from("v3_h10_asset_consensus_30m")
    .select("cohort_id,coin,cohort_role,independent_wallets_30m,bullish_wallets_30m,bearish_wallets_30m,net_exposure_change_quote_30m,gross_fill_notional_quote_30m,last_activity_time_30m")
    .eq("coin",coin).eq("cohort_role","PRIMARY")
    .order("last_activity_time_30m",{ascending:false}).limit(1).maybeSingle();
  if(error)return respond(503,{ok:false,error:"source_read_unavailable"});
  const last=Date.parse(data?.last_activity_time_30m??"");
  const now=Date.now();
  if(!data||!Number.isFinite(last)||last>now+1000||now-last>1800000)
    return respond(200,{ok:true,status:"NOT_AVAILABLE_OR_STALE",pair,
      sources:{},orders:false,model_called:false});
  const n=Number(data.independent_wallets_30m),
        bulls=Number(data.bullish_wallets_30m),
        bears=Number(data.bearish_wallets_30m),
        net=Number(data.net_exposure_change_quote_30m),
        gross=Number(data.gross_fill_notional_quote_30m);
  if(![n,bulls,bears,net,gross].every(Number.isFinite)||
      n<1||bulls<0||bears<0||bulls+bears>n)
    return respond(200,{ok:true,status:"NOT_EVALUABLE_SOURCE_COUNTS",pair,
      sources:{},orders:false,model_called:false});
  // A few wallets are not proof of a genuine multi-wallet, self-dealing-
  // screened buying catalyst. Never assert the positive SOURCE_CATALYST
  // fields 'onchain_fills_confirmed' or 'not_self_dealing_checked' here.
  const direction=(bulls>bears&&net>0)?"LONG":
      (bears>bulls&&net<0)?"SHORT":"MIXED";
  const observed=new Date(last).toISOString();
  const captured=new Date(now).toISOString();
  const snapshot={
    pair,source_verified:true,
    source_owner:"EXISTING_H10_HYPERLIQUID_PROSPECTIVE_CAPTURE",
    source_id:"v3_h10_asset_consensus_30m",
    observed_at_utc:observed,known_at_utc:captured,
    cohort_id:String(data.cohort_id??"").slice(0,80),
    consensus_direction:direction,independent_wallet_count:n,
    source_fill_seen_at_utc:observed,
    // Purely descriptive until actually validated original fills.
    research_consensus_not_buy_authority:true,
    approximate_net_exposure_change_quote:net,
    approximate_gross_fill_notional_quote:gross
  };
  return respond(200,{ok:true,status:"H10_PIT_CONTEXT_ONLY",
    pair,sources:{smart_money_h10:snapshot},
    paper_only:true,orders:false,model_called:false,
    no_positive_source_catalyst_asserted:true});
});
