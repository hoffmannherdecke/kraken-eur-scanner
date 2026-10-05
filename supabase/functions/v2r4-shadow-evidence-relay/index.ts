import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "npm:@supabase/supabase-js@2";

type EvidenceRecord = {
  event_id?: unknown;
  pair?: unknown;
  observed_at?: unknown;
  event_payload?: unknown;
  outcome_status?: unknown;
  outcome_payload?: unknown;
  source_runtime_commit?: unknown;
};

const jsonHeaders = { "Content-Type": "application/json" };
const MAX_FUTURE_MS = 5 * 60 * 1000;
const MAX_EVENT_AGE_MS = 14 * 24 * 60 * 60 * 1000;

function response(status: number, body: Record<string, unknown>) {
  return new Response(JSON.stringify(body), { status, headers: jsonHeaders });
}

function stable(value: unknown): string {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return "[" + value.map(stable).join(",") + "]";
  const obj = value as Record<string, unknown>;
  return "{" + Object.keys(obj).sort().map(k => JSON.stringify(k)+":"+stable(obj[k])).join(",") + "}";
}

async function sha24(material: string): Promise<string> {
  const data = new TextEncoder().encode(material);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2,"0")).join("").slice(0,24);
}

Deno.serve(async (req: Request) => {
  if (req.method !== "POST") return response(405, { ok:false, error:"method_not_allowed" });

  // Compatibility auth during the local-token transition. The client-specific
  // header prevents accidental cross-wiring; payload integrity/immutability below
  // limits blast radius even while the legacy secret is still shared.
  const expected = Deno.env.get("ALTRADY_WEBHOOK_TOKEN") ?? "";
  const supplied = req.headers.get("X-Shadow-Evidence-Token") ?? "";
  if (!expected || supplied !== expected) return response(401, { ok:false, error:"unauthorized" });

  let body: unknown;
  try { body = await req.json(); }
  catch { return response(400, { ok:false, error:"invalid_json" }); }

  const records = (body as {records?:unknown})?.records;
  if (!Array.isArray(records) || records.length < 1 || records.length > 100) {
    return response(400, { ok:false, error:"records_must_be_array_1_to_100" });
  }

  const url = Deno.env.get("SUPABASE_URL") ?? "";
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY") ?? "";
  if (!url || !serviceKey) return response(500, {ok:false,error:"server_credentials_missing"});
  const admin = createClient(url,serviceKey,{auth:{persistSession:false,autoRefreshToken:false}});

  const nowMs=Date.now();
  const nowIso=new Date(nowMs).toISOString();
  const bases: Record<string,unknown>[]=[];
  const outcomeRecords: Array<{event_id:string,pair:string,observed_at:string,status:string,payload:Record<string,unknown>}>=[];

  for (const raw of records as EvidenceRecord[]) {
    const eventId=typeof raw?.event_id==="string" ? raw.event_id.trim() : "";
    const pair=typeof raw?.pair==="string" ? raw.pair.trim() : "";
    const observedAt=typeof raw?.observed_at==="string" ? raw.observed_at.trim() : "";
    const eventPayload=raw?.event_payload as Record<string,unknown> | undefined;

    if (!/^[a-f0-9]{24}$/.test(eventId)) return response(400,{ok:false,error:"invalid_event_id"});
    if (!/^[A-Z0-9._-]+\/EUR$/.test(pair)) return response(400,{ok:false,error:"invalid_pair"});
    const dt=new Date(observedAt);
    if (!observedAt || Number.isNaN(dt.getTime())) return response(400,{ok:false,error:"invalid_observed_at"});
    const age=nowMs-dt.getTime();
    if (age < -MAX_FUTURE_MS) return response(400,{ok:false,error:"observed_at_too_far_future"});
    if (age > MAX_EVENT_AGE_MS) return response(400,{ok:false,error:"observed_at_too_old"});
    if (!eventPayload || typeof eventPayload!=="object" || Array.isArray(eventPayload)) {
      return response(400,{ok:false,error:"invalid_event_payload"});
    }
    if (eventPayload.pair !== pair) return response(400,{ok:false,error:"event_payload_pair_mismatch"});
    const payloadObserved=String(eventPayload.observed_at_utc ?? "");
    const payloadReceived=String(eventPayload.source_pair_received_at_utc ?? "");
    const payloadLast=eventPayload.last_eur;
    if (!payloadObserved || !payloadReceived || payloadLast === null || payloadLast === undefined) {
      return response(400,{ok:false,error:"event_identity_fields_missing"});
    }
    const payloadDt=new Date(payloadObserved);
    if (Number.isNaN(payloadDt.getTime()) || payloadDt.toISOString() !== dt.toISOString()) {
      return response(400,{ok:false,error:"event_payload_observed_at_mismatch"});
    }
    const expectedId=await sha24([pair,payloadObserved,payloadReceived,String(payloadLast)].join("|"));
    if (expectedId !== eventId) return response(400,{ok:false,error:"event_id_payload_hash_mismatch"});

    bases.push({
      event_id:eventId,
      pair,
      observed_at:dt.toISOString(),
      event_payload:eventPayload,
      source_runtime_commit:typeof raw.source_runtime_commit==="string" ? raw.source_runtime_commit.slice(0,64) : null,
      updated_at:nowIso,
    });

    if (raw.outcome_payload != null) {
      const status=raw.outcome_status;
      if (status!=="COMPLETE" && status!=="INCOMPLETE_TIMEOUT") {
        return response(400,{ok:false,error:"invalid_outcome_status"});
      }
      if (typeof raw.outcome_payload!=="object" || Array.isArray(raw.outcome_payload)) {
        return response(400,{ok:false,error:"invalid_outcome_payload"});
      }
      outcomeRecords.push({
        event_id:eventId,pair,observed_at:dt.toISOString(),status,
        payload:raw.outcome_payload as Record<string,unknown>
      });
    }
  }

  // Immutable event envelope: first write wins. Duplicates never rewrite event evidence.
  const {error:baseError}=await admin.from("v2r4_shadow_evidence")
    .upsert(bases,{onConflict:"event_id",ignoreDuplicates:true});
  if (baseError) {
    console.error("base evidence insert failed",baseError.message);
    return response(500,{ok:false,error:"event_insert_failed"});
  }

  let outcomeUpdates=0;
  for (const item of outcomeRecords) {
    const {data:existing,error:readError}=await admin.from("v2r4_shadow_evidence")
      .select("event_id,pair,observed_at,outcome_status,outcome_payload")
      .eq("event_id",item.event_id).maybeSingle();
    if (readError || !existing) return response(500,{ok:false,error:"event_lookup_failed"});
    if (existing.pair!==item.pair || new Date(existing.observed_at).toISOString()!==item.observed_at) {
      return response(409,{ok:false,error:"immutable_event_identity_conflict"});
    }
    if (existing.outcome_payload != null) {
      if (existing.outcome_status!==item.status || stable(existing.outcome_payload)!==stable(item.payload)) {
        return response(409,{ok:false,error:"outcome_immutable_conflict"});
      }
      continue;
    }
    const {error:updateError}=await admin.from("v2r4_shadow_evidence")
      .update({outcome_status:item.status,outcome_payload:item.payload,updated_at:nowIso})
      .eq("event_id",item.event_id)
      .is("outcome_payload",null);
    if (updateError) return response(500,{ok:false,error:"outcome_update_failed"});
    outcomeUpdates++;
  }

  return response(200,{
    ok:true,accepted:records.length,event_envelopes:bases.length,
    outcomes_present:outcomeRecords.length,outcomes_newly_written:outcomeUpdates,
    event_mutation_allowed:false,outcome_mutation_allowed:false
  });
});