"""Build out/results*.md from out/raw_<tag>.jsonl."""
import json
import platform
import socket
import statistics as st
import time

import config

C = config.CLAIMED


def pct(xs: list[float], q: float) -> float | None:
    """Percentile with linear interpolation."""
    if not xs:
        return None
    xs = sorted(xs); k = (len(xs) - 1) * q; f = int(k)
    return xs[f] + (xs[min(f + 1, len(xs) - 1)] - xs[f]) * (k - f)


def f(v, d=2) -> str:
    """Format optional float."""
    return "n/a" if v is None else f"{v:.{d}f}"


def lat(r: dict, key: str) -> float | None:
    """Seconds from end of speech to a timestamp key."""
    return r[key] - r["t_end_speech"] if key in r and "t_end_speech" in r else None


def cost(rs: list[dict]) -> dict:
    """List-price cost per minute of caller audio and of caller+agent audio."""
    tot, cin, aout = 0.0, 0.0, 0.0
    P = config.PRICE_PER_M
    for r in rs:
        u = r.get("usage") or {}
        def tok(det, mod):
            return sum(d["token_count"] for d in u.get(det, []) or [] if d.get("modality") == mod and "token_count" in d)
        ai, ti = tok("prompt_tokens_details", "AUDIO"), tok("prompt_tokens_details", "TEXT")
        ao, to = tok("response_tokens_details", "AUDIO"), tok("response_tokens_details", "TEXT")
        th = u.get("thoughts_token_count", 0) or 0
        tot += (ai * P["audio_in"] + ao * P["audio_out"] + ti * P["text_in"] + (to + th) * P["text_out"]) / 1e6
        cin += r["audio_in_s"]; aout += r.get("audio_out_s", 0)
    if not rs or cin == 0:
        return {}
    return {"total": tot, "per_caller_min": tot / (cin / 60), "per_total_min": tot / ((cin + aout) / 60)}


def stats(rs: list[dict]) -> dict:
    """Compute TTFA/total stats over ok records."""
    ok = [r for r in rs if r["outcome"] == "ok" and "t_turn_complete" in r]
    m = [r for r in ok if r["query"] not in config.EXCLUDE_MATCHED]
    t = [lat(r, "t_first_audio") for r in m]; tt = [lat(r, "t_turn_complete") for r in m]
    return {"n_ok": len(ok), "n_matched": len(m), "ttfa_p50": pct(t, .5), "ttfa_p95": pct(t, .95),
            "total_p50": pct(tt, .5), "all_ttfa": [lat(r, "t_first_audio") for r in ok]}


def verdict(meas, claimed) -> str:
    """Reproduced if within 25%."""
    if meas is None:
        return "Cannot assess"
    return "Reproduced" if abs(meas - claimed) / claimed <= 0.25 else "Not reproduced"


def net_rtt() -> str:
    """Rough TCP connect time to Google API."""
    try:
        t = time.perf_counter(); socket.create_connection(("generativelanguage.googleapis.com", 443), 5).close()
        return f"{(time.perf_counter()-t)*1000:.0f} ms TCP connect"
    except OSError as e:
        return f"unmeasured ({e})"


def main(tag: str = "vad200", vad: str = "") -> dict:
    """Write results_<tag>.md and return headline numbers."""
    rs = [json.loads(l) for l in open(config.OUT_DIR / f"raw_{tag}.jsonl", encoding="utf-8")]
    p1 = [r for r in rs if r["pass_no"] == 1]
    S1, SA = stats(p1), stats(rs)
    L = ["# S2S demo results", "",
         "**KB is STAND-IN (invented). Questions are SYNTHETIC TTS audio (likely easier than real callers). Answer quality not assessed; latency and cost only.**", "",
         "## Claimed vs measured (12 matched queries, q11/q12 excluded)", "",
         "| Metric | Claimed | Pass 1 | All passes | Delta (all) |", "|---|---|---|---|---|"]
    for name, key in [("TTFA p50 (s)", "ttfa_p50"), ("TTFA p95 (s)", "ttfa_p95"), ("Total p50 (s)", "total_p50")]:
        d = None if SA[key] is None else SA[key] - C[key]
        L.append(f"| {name} | {C[key]} | {f(S1[key])} | {f(SA[key])} | {f(d)} |")
    ok1 = len({r["query"] for r in p1 if r["outcome"] == "ok"})
    L += [f"| Success | {C['success']} | {ok1}/14 | {sum(r['outcome']=='ok' for r in rs)}/{len(rs)} calls | |", ""]
    L += ["TTFA includes the 300 ms appended silence, measured from the end of caller speech.", "",
          f"n matched ok: pass1={S1['n_matched']}, all={SA['n_matched']}.", ""]
    L += ["## Tool calls", "", "| query | pass | time-to-tool-call (s) | tool-call to response sent (s) | kb ms |", "|---|---|---|---|---|"]
    ttc = []
    for r in rs:
        a = lat(r, "t_tool_call")
        if a is not None:
            ttc.append(a)
        gap = r["t_tool_resp"] - r["t_tool_call"] if "t_tool_resp" in r and "t_tool_call" in r else None
        kms = ", ".join(f"{c['kb_ms']:.2f}" for c in r.get("kb_calls", []))
        L.append(f"| {r['query']} | {r['pass_no']} | {f(a,3)} | {f(gap,4)} | {kms} |")
    L += ["", f"Time-to-tool-call p50/p95: {f(pct(ttc,.5),3)} / {f(pct(ttc,.95),3)} s over {len(ttc)} calls; "
          f"{sum(1 for r in rs if r['outcome']=='ok' and 'kb_calls' not in r)} ok turns made no tool call.", ""]
    L += ["## Failures and retries", ""]
    bad = [(r, a) for r in rs for a in r["attempts"] if a["outcome"] != "ok"]
    if not bad:
        L.append("None.")
    for r, a in bad:
        L.append(f"- {r['query']} pass {r['pass_no']} attempt {a['attempt']}: {a['outcome']} {a['error'] or ''}")
    final_bad = [r for r in rs if r["outcome"] != "ok"]
    L += ["", f"Final-outcome failures: {len(final_bad)} of {len(rs)} (quota 429/503: {sum(r['outcome']=='quota_429_503' for r in final_bad)}).", ""]
    c = cost(rs)
    L += ["## Cost (list-price equivalent; free tier actually $0)", ""]
    if c:
        near = "per caller-minute" if abs(c["per_caller_min"] - C["cost_min"]) < abs(c["per_total_min"] - C["cost_min"]) else "per total-minute"
        L += [f"- Per minute of caller audio: ${c['per_caller_min']:.4f}", f"- Per minute of caller+agent audio: ${c['per_total_min']:.4f}",
              f"- Claimed $0.0164 is closer to the {near} figure. Verdict: {verdict(c['per_caller_min'] if near=='per caller-minute' else c['per_total_min'], C['cost_min'])}.",
              "- Token counts taken from the last usage_metadata message per turn (assumed cumulative); thought tokens billed as text output."]
    else:
        L.append("Cannot assess (no usage metadata).")
    pt, pc = S1["ttfa_p50"], S1["ttfa_p95"]
    L += ["", "## Verdicts", "",
          f"- TTFA p50 (all): {verdict(SA['ttfa_p50'], C['ttfa_p50'])}", f"- TTFA p95 (all): {verdict(SA['ttfa_p95'], C['ttfa_p95'])}",
          f"- Total p50 (all): {verdict(SA['total_p50'], C['total_p50'])}",
          f"- Success 14/14 (pass 1): {'Reproduced' if ok1 == 14 else 'Not reproduced'} ({ok1}/14)",
          f"- Acceptance (p50 < 2 s and p95 < 3 s): " + ("Cannot assess" if SA['ttfa_p50'] is None else
            "PASS" if SA['ttfa_p50'] < 2 and SA['ttfa_p95'] < 3 else "FAIL"), "",
          "## Environment", "", f"- Host: {platform.node()} ({platform.platform()}), local machine, Python {platform.python_version()}",
          f"- Network: {net_rtt()}", f"- Models used: {sorted({r['model'] for r in rs})}", f"- VAD: {vad}",
          f"- Chunk {config.CHUNK_MS} ms, silence {config.SILENCE_MS} ms, gap {config.GAP_S}s, passes {config.PASSES}"]
    (config.OUT_DIR / f"results_{tag}.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    ok = [r for r in rs if r["outcome"] == "ok" and "t_turn_complete" in r and r["query"] not in config.EXCLUDE_MATCHED]
    au = [r["audio_out_s"] for r in ok]
    span = [r["t_turn_complete"] - r["t_first_audio"] - r["audio_out_s"] for r in ok]
    return {"p1": S1, "all": SA, "ok1": ok1, "calls_ok": sum(r["outcome"] == "ok" for r in rs), "n": len(rs),
            "audio_p50": pct(au, .5), "tail_p50": pct(span, .5), "cost": c, "vad": vad,
            "ttc_p50": pct(ttc, .5), "retries": sum(len(r["attempts"]) - 1 for r in rs)}


def combine() -> None:
    """Write out/results.md with both VAD runs side by side."""
    runs = [("vad200", "VAD silence 200 ms"), ("vaddefault", "VAD server default")]
    R = {t: main(t, lab) for t, lab in runs
         if (config.OUT_DIR / f"raw_{t}.jsonl").exists()}
    L = ["# S2S demo results (both VAD runs)", "",
         "**KB is STAND-IN (invented). Questions are SYNTHETIC TTS audio (q01-q11 gemini-2.5-flash-preview-tts, q12-q14 gemini-3.8-flash-tts after the free daily TTS quota ran out; likely easier than real callers). Latency and cost only.**",
         "All runs: 300 ms appended silence, then silence frames keep streaming until the turn ends. Latency stats on 12 matched queries per pass (q11/q12 excluded).", "",
         "| Metric | Claimed | " + " | ".join(f"{R[t]['vad']} (all / pass 1)" for t in R) + " |", "|---|---|" + "---|" * len(R)]
    for name, key in [("TTFA p50 (s)", "ttfa_p50"), ("TTFA p95 (s)", "ttfa_p95"), ("Total p50 (s)", "total_p50")]:
        L.append(f"| {name} | {C[key]} | " + " | ".join(f"{f(R[t]['all'][key])} / {f(R[t]['p1'][key])}" for t in R) + " |")
    L.append(f"| Success (calls ok) | 14/14 | " + " | ".join(f"{R[t]['calls_ok']}/{R[t]['n']} (pass 1: {R[t]['ok1']}/14)" for t in R) + " |")
    L.append("| Agent answer audio p50 (s) | n/a | " + " | ".join(f(R[t]["audio_p50"]) for t in R) + " |")
    L.append("| turn_complete minus (first audio + answer audio) p50 (s) | n/a | " + " | ".join(f(R[t]["tail_p50"]) for t in R) + " |")
    L.append("| Cost per caller-min / total-min (list price) | 0.0164 | " + " | ".join(
        (f"${R[t]['cost']['per_caller_min']:.4f} / ${R[t]['cost']['per_total_min']:.4f}" if R[t]["cost"] else "n/a") for t in R) + " |")
    L.append("| Retries | | " + " | ".join(str(R[t]["retries"]) for t in R) + " |")
    L += ["", "## Why total response is about 7.6 s (diagnosis)", "",
          "Total = TTFA + spoken length of the answer. turn_complete arrives at about first-audio time + answer audio duration (the row above is about 0 s, so there is no extra turn-end wait). The model speaks in real time, and the STAND-IN KB passages are read nearly verbatim (about 6 s of audio). The claimed 2.50 s total is only consistent with a much shorter answer, so it was measured with different (shorter) answers, or TTFA-style timing. Not tuned to match.", "",
          "Per-run detail: results_vad200.md, results_vaddefault.md, results_run1_no_keepalive.md (first run without silence keep-alive, 21/42 timeouts).", ""]
    (config.OUT_DIR / "results.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("wrote out/results.md")


if __name__ == "__main__":
    combine()
