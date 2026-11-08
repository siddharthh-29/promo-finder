"""Parse Kuku-style timestamped screenplay .txt files into structured events.

Format (case of labels varies between episodes, so everything is case-insensitive):
  EPISODE NUMBER / EPISODE LOGLINE / CONTINUITY NOTES
  SCENE NN / Scene heading / Scene start / Scene end
  **SPEAKER (tone):**  then  Start: (mm:ss.ff) | End: (mm:ss.ff)  then text
"""
import re, glob, os
from dataclasses import dataclass, field, asdict

TS = r"(?:(\d+):)?(\d+):(\d+(?:\.\d+)?)"          # [h:]mm:ss.ff
BLOCK_RE = re.compile(r"^\*\*(.+?):\*\*\s*$")
TIME_RE = re.compile(rf"Start:\s*\({TS}\)\s*\|\s*End:\s*\({TS}\)", re.I)
VISUAL_KINDS = {"CAMERA"}
NONSPEECH = {"CAMERA", "ACTION", "SOUND FX", "SFX", "MUSIC", "TEXT", "TITLE"}


def to_sec(h, m, s):
    return int(h or 0) * 3600 + int(m) * 60 + float(s)


@dataclass
class Event:
    id: int
    scene: int
    kind: str            # CAMERA | ACTION | SOUND FX | DIALOGUE
    speaker: str         # character name for DIALOGUE else ""
    tone: str
    start: float
    end: float
    text: str


@dataclass
class Episode:
    number: int
    logline: str = ""
    continuity: str = ""
    duration: float = 0.0
    scenes: list = field(default_factory=list)   # {n, heading, start, end}
    events: list = field(default_factory=list)   # list[Event]
    warnings: list = field(default_factory=list)


def _meta(text, key):
    m = re.search(rf"^{key}:\s*(.+)$", text, re.I | re.M)
    return m.group(1).strip() if m else ""


def parse_episode(path):
    raw = open(path, encoding="utf-8").read()
    fn = re.search(r"episode-(\d+)", os.path.basename(path), re.I)
    num_m = re.search(r"EPISODE NUMBER:\s*Episode\s*(\d+)", raw, re.I)
    num = int(num_m.group(1)) if num_m else (int(fn.group(1)) if fn else 0)
    ep = Episode(number=num, logline=_meta(raw, "EPISODE LOGLINE"),
                 continuity=_meta(raw, "CONTINUITY NOTES"))
    lines = raw.splitlines()
    scene = 0
    i, n = 0, len(lines)
    while i < n:
        ln = lines[i].strip()
        sm = re.match(r"^SCENE\s+(\d+)\s*$", ln, re.I)
        if sm:
            scene = int(sm.group(1))
            hd = st = en = None
            j = i + 1
            while j < n and j < i + 8:
                l2 = lines[j].strip()
                if BLOCK_RE.match(l2):      # header ended; don't swallow the first block
                    break
                if re.match(r"scene heading:", l2, re.I): hd = l2.split(":", 1)[1].strip()
                mm = re.match(rf"scene (start|end):\s*{TS}", l2, re.I)
                if mm:
                    v = to_sec(mm.group(2), mm.group(3), mm.group(4))
                    if mm.group(1).lower() == "start": st = v
                    else: en = v
                j += 1
            ep.scenes.append(dict(n=scene, heading=hd or "", start=st or 0.0, end=en or 0.0))
            i = j
            continue
        bm = BLOCK_RE.match(ln)
        if bm and i + 1 < n:
            tm = TIME_RE.search(lines[i + 1])
            if not tm:
                ep.warnings.append(f"block without timestamps near line {i+1}: {ln[:40]}")
                i += 1
                continue
            g = tm.groups()
            start, end = to_sec(*g[0:3]), to_sec(*g[3:6])
            body, j = [], i + 2
            while j < n and not BLOCK_RE.match(lines[j].strip()) \
                    and not re.match(r"^(SCENE\s+\d+|--- SCRIPT END ---)", lines[j].strip(), re.I):
                if lines[j].strip(): body.append(lines[j].strip())
                j += 1
            label = bm.group(1).strip()
            tone_m = re.match(r"^(.*?)\s*\((.*)\)\s*$", label)
            name, tone = (tone_m.group(1), tone_m.group(2)) if tone_m else (label, "")
            up = name.upper()
            kind = up if up in NONSPEECH else "DIALOGUE"
            if end < start:
                ep.warnings.append(f"end<start at {start}"); end = start
            ep.events.append(Event(len(ep.events), scene, kind,
                                   name if kind == "DIALOGUE" else "", tone,
                                   start, end, " ".join(body).strip('" ')))
            i = j
            continue
        i += 1
    ep.duration = max([s["end"] for s in ep.scenes] + [e.end for e in ep.events] + [0])
    if not ep.events: ep.warnings.append("no events parsed")
    return ep


def load_pack(folder):
    files = sorted(glob.glob(os.path.join(folder, "**", "episode-*.txt"), recursive=True))
    eps = [parse_episode(f) for f in files]
    return sorted(eps, key=lambda e: e.number)


def fmt(t):
    return f"{int(t)//60:02d}:{t%60:05.2f}"

if __name__ == "__main__":
    import sys
    eps = load_pack(sys.argv[1])
    for e in eps:
        k = sum(1 for x in e.events if x.kind == "DIALOGUE")
        print(f"Ep{e.number:>2} dur={fmt(e.duration)} scenes={len(e.scenes)} events={len(e.events)} dialogue={k} warn={len(e.warnings)}")
