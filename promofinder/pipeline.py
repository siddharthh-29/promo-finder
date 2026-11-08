import json, re
from .parse import fmt
from .candidates import generate, MIN_S, MAX_S, BEATS

SYSTEM = """You are a senior promo editor for vertical microdrama (ReelShort/DramaBox style).
Pick the best PROMO CLIPS from ONE episode screenplay. A promo is 20-60 seconds taken from the show, posted to pull in viewers who have NEVER seen it. A good promo:
1. HOOK: in the first 3 seconds something makes a scroller stop (a slap, reveal, shocking line, threat, public humiliation).
2. CLIFFHANGER: it cuts at an unresolved moment so the viewer must know what happens next. Never end on a resolved/calm beat.
3. STANDS ALONE: a stranger understands who is who and what is at stake without earlier episodes. Reject clips that open on a reply like "Why?" or "Fine." with no setup, or that depend on a prior-episode reveal.
Rules: you choose beats ONLY by their [id]. Never write timestamps. Clip = beats start_id..end_id inclusive, must total 20-60s. Prefer 30-50s. Return at most 3 promos per episode, fewer (or none) if the episode has no strong moment. Do not return overlapping clips.
Return ONLY JSON: {"promos":[{"start_id":int,"end_id":int,"hook":"what the first 3s is","cliffhanger":"the unresolved question at the end","why":"one line","hook_score":1-10,"cliff_score":1-10,"standalone_score":1-10,"context_needed":"what a new viewer would be missing, or none"}]}"""


def render(ep, cands):
    out = [f"EPISODE {ep.number}", f"LOGLINE: {ep.logline}", f"CONTINUITY: {ep.continuity}", "", "BEATS:"]
    for e in ep.events:
        if e.kind not in BEATS: continue
        who = f"{e.speaker} ({e.tone})" if e.kind == "DIALOGUE" else e.kind
        out.append(f"[{e.id}] {fmt(e.start)}-{fmt(e.end)} {who}: {e.text[:220]}")
    out += ["", "RULE-BASED SHORTLIST (hints only; you may disagree):"]
    for c in cands:
        out.append(f"- beats {c.i0}..{c.i1} ({c.dur:.0f}s) hook_rule={c.h_hook:.1f} cliff_rule={c.h_cliff:.1f}")
    return "\n".join(out)


def validate(ep, p):
    """Turn a model pick into a checked promo. Timestamps come from the data, never from the model."""
    by_id = {e.id: e for e in ep.events}
    a, b = p.get("start_id"), p.get("end_id")
    if a not in by_id or b not in by_id or a > b: return None, "bad beat ids"
    span = [e for e in ep.events[a:b + 1] if e.kind in BEATS]
    if not span: return None, "empty span"
    st, en = min(e.start for e in span), max(e.end for e in span)
    note = ""
    # trim leading beats if too long (keeps the cliffhanger end intact)
    while en - st > MAX_S and len(span) > 1:
        span = span[1:]; st = min(e.start for e in span); note = "trimmed start to fit 60s"
    d = en - st
    if d < MIN_S: return None, f"too short ({d:.0f}s)"
    if d > MAX_S: return None, f"too long ({d:.0f}s)"
    return dict(start=st, end=en, a=span[0].id, b=span[-1].id, note=note), ""


def overlap(p, q):
    return p["episode"] == q["episode"] and min(p["end"], q["end"]) - max(p["start"], q["start"]) > 0.3 * min(p["end"] - p["start"], q["end"] - q["start"])


def score(p):
    """Final rank score 0-10. LLM judgment dominates; rules are a tie-break."""
    return round(0.35 * p["hook_score"] + 0.35 * p["cliff_score"] + 0.25 * p["standalone_score"]
                 + 0.05 * min(p["rule_total"], 14) / 14 * 10, 2)


def mock_judge(user):
    """Offline stand-in for a model: takes the rule shortlist's top 2. For plumbing tests only."""
    ids = re.findall(r"beats (\d+)\.\.(\d+) \((\d+)s\) hook_rule=([\d.]+) cliff_rule=([\d.]+)", user)
    picks = []
    for a, b, d, h, c in ids[:2]:
        picks.append(dict(start_id=int(a), end_id=int(b), hook="(mock)", cliffhanger="(mock)", why="mock",
                          hook_score=min(10, float(h) + 2), cliff_score=min(10, float(c) + 2),
                          standalone_score=5, context_needed="unknown"))
    return json.dumps({"promos": picks})


def run_episode(ep, llm=None, top_k=6):
    cands, n_raw = generate(ep, top_k=top_k)
    promos, rejected = [], []
    if llm is None:                                         # rules-only baseline
        raw = [dict(start_id=c.i0, end_id=c.i1, hook=c.opens_with, cliffhanger=c.closes_with,
                    why="rule-based pick (no LLM)", hook_score=min(10, c.h_hook * 1.25),
                    cliff_score=min(10, c.h_cliff * 1.25), standalone_score=5, context_needed="not assessed")
               for c in cands[:3]]
    else:
        res = llm.json(SYSTEM, render(ep, cands), mock_fn=mock_judge)
        raw = res.get("promos", []) if isinstance(res, dict) else res
    for p in raw:
        v, why = validate(ep, p)
        if v is None: rejected.append(dict(episode=ep.number, pick=p, reason=why)); continue
        rule = next((c.h_total for c in cands if c.i0 <= v["a"] and c.i1 >= v["b"]), 0.0)
        item = dict(episode=ep.number, start=v["start"], end=v["end"],
                    segments=[dict(episode=ep.number, start=fmt(v["start"]), end=fmt(v["end"]))],
                    hook=p.get("hook", ""), cliffhanger=p.get("cliffhanger", ""), why=p.get("why", ""),
                    hook_score=float(p.get("hook_score", 0)), cliff_score=float(p.get("cliff_score", 0)),
                    standalone_score=float(p.get("standalone_score", 0)),
                    context_needed=p.get("context_needed", ""), rule_total=rule, adjust=v["note"],
                    duration_s=round(v["end"] - v["start"], 1), beats=[v["a"], v["b"]])
        item["score"] = score(item)
        if not any(overlap(item, q) for q in promos): promos.append(item)
    return promos, rejected, n_raw
