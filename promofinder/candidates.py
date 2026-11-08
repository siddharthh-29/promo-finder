"""Candidate generation (pure code, no LLM): every 20-60s window whose start/end snap to beat
boundaries, scored by cheap rules. The LLM only ever sees the best few per episode."""
import re
from dataclasses import dataclass, asdict
from .parse import fmt

MIN_S, MAX_S = 20.0, 60.0
BEATS = {"DIALOGUE", "ACTION", "SOUND FX"}

HOOK_WORDS = r"slap|strike|struck|slam|shove|drag|grab|seize|collaps|gasp|scream|shriek|shout|tear|blood|dagger|sword|knife|poison|kneel|throw|hurl|burst|shatter|rip|faint"
SHOCK_WORDS = r"divorce|betray|pregnan|secret|duke|king|prince|dead|death|kill|murder|lie[sd]?|liar|traitor|truth|reveal|who are you|you\b.*\bare\b.*\b(?:the|a)\b|impossible|how dare|dare you|get out|guards|arrest|execute|marry|wife|husband|bastard|heir|crown|poison|forgive|never|monster"
TONE_HOT = r"shock|furious|rage|scream|cold|menac|threat|stun|horrif|desperate|sneer|cruel|venom|trembl|disbelie|defian|gasp|ominous|sinister"
STING = r"cliffhanger|sting|ominous|swell|stab|dramatic|dissonan|abrupt|silence|cut to black|heartbeat"
RESOLVED = r"thank you|i love you|forgive me|smil\w+ warmly|embrace|kiss|laugh\w*|happy|at last|safe now|peace"


@dataclass
class Candidate:
    episode: int
    start: float
    end: float
    i0: int
    i1: int
    h_hook: float = 0.0
    h_cliff: float = 0.0
    h_len: float = 0.0
    h_penalty: float = 0.0
    h_total: float = 0.0
    ends_episode: bool = False
    opens_with: str = ""
    closes_with: str = ""

    @property
    def dur(self): return self.end - self.start

    def key(self): return (self.episode, round(self.start, 2), round(self.end, 2))


def _txt(e):
    return f"{e.speaker} {e.tone} {e.text}".lower()


def _hook_score(first_events):
    """Rules for 'something in the first 3 seconds that makes a scroller stop'."""
    s = 0.0
    for e in first_events:
        t = _txt(e)
        if e.kind == "DIALOGUE":
            s += 1.0
            if "!" in e.text: s += 1.0
            if "?" in e.text: s += 0.8
            if len(e.text.split()) <= 9: s += 0.5          # short punchy line
            if re.search(SHOCK_WORDS, t): s += 1.5
            if re.search(TONE_HOT, e.tone.lower()): s += 1.0
        elif e.kind == "ACTION":
            if re.search(HOOK_WORDS, t): s += 2.5
            else: s += 0.3
        elif e.kind == "SOUND FX":
            if re.search(r"slap|crash|shatter|gasp|scream|impact|thud", t): s += 1.5
    return min(s, 8.0)


def _cliff_score(last_events, ends_episode):
    s = 0.0  # episode boundaries alone do not make a cliffhanger
    for k, e in enumerate(reversed(last_events)):
        w = 1.0 / (1 + k * 0.6)                           # last beats matter most
        t = _txt(e)
        if e.kind == "DIALOGUE":
            if e.text.rstrip().endswith("?"): s += 1.5 * w
            if e.text.rstrip().endswith(("...", "—", "-")): s += 1.2 * w
            if "!" in e.text: s += 0.6 * w
            if re.search(SHOCK_WORDS, t): s += 1.3 * w
            if re.search(TONE_HOT, e.tone.lower()): s += 0.6 * w
        elif e.kind == "SOUND FX" and re.search(STING, t): s += 0.35 * w  # punctuation, not the cliffhanger itself
        elif e.kind == "ACTION" and re.search(HOOK_WORDS, t): s += 1.2 * w
        if re.search(RESOLVED, t): s -= 1.2 * w            # resolved/happy beat = weak ending
    return max(min(s, 8.0), 0.0)


def generate(ep, top_k=6, min_gap=12.0):
    beats = [e for e in ep.events if e.kind in BEATS]
    cands = []
    for a in range(len(beats)):
        st = beats[a].start
        for b in range(a, len(beats)):
            en = max(x.end for x in beats[a:b + 1])
            d = en - st
            if d > MAX_S: break
            if d < MIN_S: continue
            # a clip must END on a dialogue/action beat (not mid sound-fx), and START on speech/action
            if beats[b].kind == "SOUND FX" and not re.search(STING, _txt(beats[b])): continue
            if beats[a].kind == "SOUND FX": continue
            first = [x for x in beats[a:b + 1] if x.start - st <= 3.0]
            last = [x for x in beats[a:b + 1] if en - x.end <= 6.0]
            ends_ep = (ep.duration - en) <= 1.5
            # Describe the final dramatic beat, not a trailing music/sting cue.
            meaningful_end = next((x for x in reversed(last) if x.kind in {"DIALOGUE", "ACTION"}), beats[b])
            c = Candidate(ep.number, st, en, beats[a].id, beats[b].id, ends_episode=ends_ep,
                          opens_with=(beats[a].text or "")[:90],
                          closes_with=(meaningful_end.text or "")[:90])
            c.h_hook = _hook_score(first)
            c.h_cliff = _cliff_score(last, ends_ep)
            c.h_len = 1.0 - min(abs(d - 40.0) / 20.0, 1.0)   # prefer ~30-50s
            # penalty: opens on a reply/reaction with no setup (starts with a bare 'yes/no/but/and')
            opening = (beats[a].text or "").strip().lower()
            if re.match(r"^(and|but|so|yes|no|then|because|he|she|they|it)\\b", opening):
                c.h_penalty += 1.0
            # Short, context-dependent replies rarely work as standalone cold opens.
            if beats[a].kind == "DIALOGUE" and len(opening.split()) <= 2 and not re.search(SHOCK_WORDS, opening):
                c.h_penalty += 0.5 if opening.endswith("?") else 1.0
            c.h_total = 1.0 * c.h_hook + 1.3 * c.h_cliff + 1.5 * c.h_len - c.h_penalty
            cands.append(c)
    # keep best, non-overlapping-ish (greedy NMS by time overlap)
    cands.sort(key=lambda c: -c.h_total)
    kept = []
    for c in cands:
        if all(min(c.end, k.end) - max(c.start, k.start) < (1 - 0.35) * min(c.dur, k.dur) or False
               for k in kept):
            kept.append(c)
        if len(kept) >= top_k: break
    return kept, len(cands)
