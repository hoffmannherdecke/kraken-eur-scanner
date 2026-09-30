import { withSupabase } from "npm:@supabase/server";

function response(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

function safeNumber(value: unknown): number | null {
  if (value === null || value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

async function sha256Hex(text: string): Promise<string> {
  const bytes = new TextEncoder().encode(text);
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return [...new Uint8Array(digest)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function sameToken(a: string, b: string): boolean {
  if (a.length !== b.length || a.length < 24) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

Deno.serve(
  withSupabase({ auth: "none" }, async (req, ctx) => {
    const configuredToken = Deno.env.get("ALTRADY_WEBHOOK_TOKEN") ?? "";
    if (!configuredToken) {
      return response({ error: "relay not configured" }, 503);
    }

    // MINI-PC poll / ack callers use a header. Altrady alerts cannot set custom
    // headers, so ingress may carry the same dedicated token in the JSON Note.
    if (req.method === "GET") {
      const supplied = req.headers.get("x-altrady-relay-token") ?? "";
      if (!sameToken(configuredToken, supplied)) return response({ error: "unauthorized" }, 401);

      const limitRaw = Number(new URL(req.url).searchParams.get("limit") ?? "20");
      const limit = Math.max(1, Math.min(50, Number.isFinite(limitRaw) ? limitRaw : 20));

      const { data, error } = await ctx.supabaseAdmin
        .from("altrady_trigger_events")
        .select("id,event_key,exchange,symbol,direction,close_price,event_time,low_price,high_price,received_at")
        .eq("status", "pending")
        .order("received_at", { ascending: true })
        .limit(limit);

      if (error) return response({ error: "database read failed" }, 500);
      return response({ ok: true, events: data ?? [] });
    }

    if (req.method !== "POST") return response({ error: "GET or POST only" }, 405);

    const url = new URL(req.url);
    const mode = url.searchParams.get("mode") ?? "ingest";

    if (mode === "ack") {
      const supplied = req.headers.get("x-altrady-relay-token") ?? "";
      if (!sameToken(configuredToken, supplied)) return response({ error: "unauthorized" }, 401);

      let payload: any;
      try {
        payload = await req.json();
      } catch {
        return response({ error: "invalid JSON" }, 400);
      }
      const ids = Array.isArray(payload?.ids) ? payload.ids.filter((x: unknown) => typeof x === "string").slice(0, 50) : [];
      if (!ids.length) return response({ error: "ids required" }, 400);

      const { error } = await ctx.supabaseAdmin
        .from("altrady_trigger_events")
        .update({
          status: "consumed",
          processed_at: new Date().toISOString(),
          processed_by: "minipc-altrady-poller",
        })
        .in("id", ids)
        .eq("status", "pending");

      if (error) return response({ error: "database ack failed" }, 500);
      return response({ ok: true, acknowledged: ids.length });
    }

    const raw = await req.text();
    if (raw.length > 8192) return response({ error: "payload too large" }, 413);

    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(raw);
    } catch {
      return response({ error: "JSON Note required" }, 400);
    }

    const supplied = typeof payload.token === "string" ? payload.token : "";
    if (!sameToken(configuredToken, supplied)) return response({ error: "unauthorized" }, 401);

    // Never persist the shared secret.
    const sanitized = { ...payload };
    delete sanitized.token;

    const exchange = typeof sanitized.exchange === "string" ? sanitized.exchange.slice(0, 64) : null;
    const symbol = typeof sanitized.symbol === "string" ? sanitized.symbol.slice(0, 64) : null;
    const direction = typeof sanitized.direction === "string" ? sanitized.direction.slice(0, 32) : null;
    const eventTime = typeof sanitized.time === "string" ? sanitized.time.slice(0, 128) : null;

    if (!symbol) return response({ error: "symbol required" }, 400);

    const stable = JSON.stringify({
      exchange,
      symbol,
      direction,
      close: sanitized.close ?? null,
      time: eventTime,
      low: sanitized.low ?? null,
      high: sanitized.high ?? null,
    });
    const eventKey = "altrady:" + (await sha256Hex(stable));

    const row = {
      event_key: eventKey,
      exchange,
      symbol,
      direction,
      close_price: safeNumber(sanitized.close),
      event_time: eventTime,
      low_price: safeNumber(sanitized.low),
      high_price: safeNumber(sanitized.high),
      raw_payload: sanitized,
      status: "pending",
    };

    const { data, error } = await ctx.supabaseAdmin
      .from("altrady_trigger_events")
      .upsert(row, { onConflict: "event_key", ignoreDuplicates: true })
      .select("id,event_key,received_at")
      .maybeSingle();

    if (error) return response({ error: "database write failed" }, 500);

    return response({ ok: true, accepted: true, event: data ?? { event_key: eventKey } });
  })
);
