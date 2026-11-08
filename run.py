"""Usage:
  python run.py --pack ./pack --out outputs/baseline                 # rules only, no API needed
  LLM_API_KEY=... python run.py --pack ./pack --out outputs/llm --llm   # LLM judge (see promofinder/llm.py)
  python run.py --pack ./pack --out outputs/mock --llm --provider mock  # offline plumbing test
Options: --episodes 1-5   --top 3 (promos kept per episode)
"""
import argparse, json, csv, os, time
from promofinder.parse import load_pack, fmt
from promofinder.pipeline import run_episode
from promofinder.llm import LLM, LLMError


def parse_range(s, allv):
    if not s: return set(allv)
    out = set()
    for part in s.split(","):
        a, _, b = part.partition("-"); out |= set(range(int(a), int(b or a) + 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pack", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--llm", action="store_true"); ap.add_argument("--provider"); ap.add_argument("--model")
    ap.add_argument("--episodes"); ap.add_argument("--sleep", type=float, default=0.0,
                    help="seconds between calls (free-tier rate limits)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    eps = load_pack(a.pack)
    want = parse_range(a.episodes, [e.number for e in eps])
    llm = LLM(provider=a.provider, model=a.model) if a.llm else None
    allp, rej, errors, raw_n = [], [], [], 0
    for ep in eps:
        if ep.number not in want: continue
        try:
            p, r, n = run_episode(ep, llm)
        except LLMError as e:
            errors.append(dict(episode=ep.number, error=str(e))); print(f"Ep{ep.number}: LLM error {e}"); continue
        allp += p; rej += r; raw_n += n
        print(f"Ep{ep.number:>2}: {n:>4} candidate windows -> {len(p)} promos, {len(r)} rejected")
        if a.sleep: time.sleep(a.sleep)
    allp.sort(key=lambda x: -x["score"])
    for i, p in enumerate(allp, 1): p["rank"] = i
    meta = dict(mode=("llm:" + llm.provider + ":" + llm.model) if llm else "rules-only",
                episodes=len(want), candidate_windows=raw_n, promos=len(allp), rejected=len(rej),
                errors=len(errors), llm_calls=getattr(llm, "calls", 0),
                approx_input_chars=getattr(llm, "in_chars", 0))
    json.dump(dict(meta=meta, promos=allp, rejected=rej, errors=errors), open(f"{a.out}/promos.json", "w"), indent=2)
    with open(f"{a.out}/promos.csv", "w", newline="") as f:
        w = csv.writer(f); w.writerow(["rank", "episode", "segments(start-end)", "duration_s", "score", "hook_score", "cliff_score", "standalone_score", "hook", "cliffhanger", "why", "context_needed"])
        for p in allp:
            w.writerow([p["rank"], p["episode"], "; ".join(f"Ep{s['episode']} {s['start']}-{s['end']}" for s in p["segments"]),
                        p["duration_s"], p["score"], p["hook_score"], p["cliff_score"], p["standalone_score"],
                        p["hook"], p["cliffhanger"], p["why"], p["context_needed"]])
    with open(f"{a.out}/ranked_report.md", "w") as f:
        f.write(f"# Promo ranking ({meta['mode']})\n\n{meta}\n\n## Top 15 - post these first\n\n")
        for p in allp[:15]:
            s = p["segments"][0]
            f.write(f"**#{p['rank']} - Ep {p['episode']} {s['start']}-{s['end']} ({p['duration_s']}s), score {p['score']}**  \n"
                    f"Hook: {p['hook']}  \nCliffhanger: {p['cliffhanger']}  \nWhy: {p['why']}  \nContext a new viewer lacks: {p['context_needed']}\n\n")
        f.write("## All promos by episode\n\n| Ep | Start-End | Dur | Score |\n|---|---|---|---|\n")
        for p in sorted(allp, key=lambda x: (x["episode"], x["start"])):
            s = p["segments"][0]; f.write(f"| {p['episode']} | {s['start']}-{s['end']} | {p['duration_s']}s | {p['score']} |\n")
    print(json.dumps(meta))

if __name__ == "__main__":
    main()
