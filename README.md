# Promo Finder (Kuku assignment, Problem 1)
Finds 20-60s promo clips (hook + cliffhanger + stands alone) in timestamped microdrama screenplays.

## Run (stdlib only, Python 3.9+, no installs)
    # put the screenplay .txt files in ./pack (NOT committed: confidential)
    python run.py --pack ./pack --out outputs/baseline                    # rules only, no API
    export LLM_API_KEY=...   # free Gemini key from aistudio.google.com
    python run.py --pack ./pack --out outputs/llm --llm --sleep 5         # LLM judge
    python run.py --pack ./pack --out outputs/x --llm --episodes 1-3      # quick trial

## Swap the model (env vars only, no code change)
    LLM_BASE_URL / LLM_MODEL / LLM_API_KEY, or LLM_PROVIDER=anthropic
See `promofinder/llm.py` for Gemini / Groq / OpenRouter presets.

## How it works
1. `parse.py`      screenplay -> events with exact times (code; verified against a raw block count, 3,727/3,727)
2. `candidates.py` all 20-60s windows snapped to beat edges, rule-scored for hook/cliffhanger (code)
3. `pipeline.py`   LLM reads one episode + shortlist, picks beats by ID, rates hook/cliffhanger/standalone
4. validation      timestamps are looked up from the data, never trusted from the model; 20-60s enforced; overlaps dropped
5. ranking         0.35 hook + 0.35 cliffhanger + 0.25 standalone + 0.05 rules


## Verified run and honest limitations
The supplied 50-episode pack was parsed into 3,727 timestamped events with zero parser warnings.
The rules-only run evaluated 16,602 candidate windows and retained 112 non-overlapping promo candidates.
All retained clips passed the 20–60 second duration validation (20.6–57.1 seconds).
See `outputs/final_rules/quality_notes.md` for spot checks and known failure cases.

The rules-only run is a baseline, not a claim that all 112 are publish-ready. In particular,
standalone context and narrative payoff are difficult to judge with keyword rules. Human review
is still required. A mock LLM run validates the model-call plumbing only; use a real API key for
semantic judging. Do not commit API keys or the confidential screenplay pack to a public repo.
