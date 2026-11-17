// ILLUSTRATION ONLY. Do not write this file by hand.
// `npm run gen` writes `src/api.gen.ts` from `openapi.json`. `openapi.json` comes from
// `saasx2x.web.openapi_json()`, which comes from the Pydantic types in `status.py`.
// This sample shows what the generator makes for `StatusBoard`.

export interface components {
  schemas: {
    Mark: "up" | "down" | "blocked" | "inconclusive" | "not_observed";
    Verdict: "up" | "down" | "blocked" | "inconclusive";
    Reason:
      | "cloudflare_challenge" | "cloudflare_block_page" | "rate_limited" | "status_ok"
      | "login_required" | "error_status" | "dns_not_found" | "tcp_failed" | "tls_failed"
      | "http_failed" | "dns_unavailable" | "probe_failed";
    WorkerState: "idle" | "fresh" | "late" | "stalled";
    Run: { mark: components["schemas"]["Mark"]; count: number };
    Strip: {
      first_slot: string; // ISO 8601, UTC
      interval_s: number;
      lead: number;
      runs: components["schemas"]["Run"][];
      readonly slot_count: number;
    };
    Tally: {
      up: number; down: number; blocked: number; inconclusive: number; not_observed: number;
      readonly uptime: number | null;
    };
    LastResult: {
      slot_start: string; probe_id: string;
      verdict: components["schemas"]["Verdict"]; reason: components["schemas"]["Reason"];
      http_status: number | null; duration_ms: number;
    };
    CheckStatus: {
      check_id: string; hostname: string; port: number; interval_s: number;
      last: components["schemas"]["LastResult"] | null;
      strip: components["schemas"]["Strip"];
      tally_24h: components["schemas"]["Tally"]; tally_7d: components["schemas"]["Tally"];
    };
    Worker: {
      state: components["schemas"]["WorkerState"];
      newest_row_at: string | null; silent_s: number | null; expected_every_s: number | null;
    };
    StatusBoard: {
      as_of: string; window_start: string;
      worker: components["schemas"]["Worker"];
      checks: components["schemas"]["CheckStatus"][];
    };
  };
}
