# Promo Finder — Kuku AI Generalist Assignment (Problem 1)

An AI-assisted system for discovering 20–60 second promotional clips from timestamped microdrama screenplays.

The system combines rule-based candidate generation with Large Language Model (LLM) evaluation to identify clips containing:
- An engaging opening hook.
- Sufficient standalone narrative context.
- A cliffhanger, reveal, escalation, or unanswered question.

## 1. Project Overview

Promo Finder processes timestamped screenplay files and produces ranked promotional clip candidates.

The prototype supports:
- Screenplay parsing and timestamp extraction.
- 20–60 second candidate window generation.
- Rule-based candidate shortlisting.
- LLM-based narrative evaluation.
- Beat ID validation and timestamp verification.
- Overlap removal and candidate ranking.
- CSV, JSON, and Markdown report generation.

## 2. Technology Stack

| Component | Technology |
|---|---|
| Programming language | Python |
| Screenplay processing | Custom Python modules |
| Candidate generation | Rule-based algorithms |
| Narrative evaluation | LLM |
| Full-run LLM | Groq-hosted Qwen 3.8 27B |
| Alternative model tested | Gemini 3.8 Flash |
| Output formats | CSV, JSON, Markdown |

The prototype uses Python standard-library modules and does not require additional Python package installations.

## 3. Project Structure

```text
promo-finder/
├── promofinder/
│   ├── __init__.py
│   ├── parse.py
│   ├── candidates.py
│   ├── llm.py
│   └── pipeline.py
├── run.py
├── README.md
└── .gitignore
```

Generated outputs and confidential screenplay files are kept outside version control.

## 4. How It Works

1. **Screenplay Parsing:** Extracts dialogue and scene beats while preserving original timestamps.
2. **Candidate Generation:** Generates contiguous 20–60 second windows snapped to screenplay beat boundaries.
3. **Rule-Based Shortlisting:** Uses lightweight scoring signals to reduce the number of candidates sent for LLM evaluation.
4. **LLM Evaluation:** Evaluates opening hooks, narrative engagement, ending strength, standalone context, and promotional suitability.
5. **Validation and Ranking:** Validates selected beat IDs against source data, derives timestamps from the screenplay, enforces duration constraints, removes overlapping selections, and ranks the results.
6. **Output Generation:** Exports promotional candidates in CSV, JSON, and Markdown formats.

The ranking formula is:

`0.35 × Hook + 0.35 × Cliffhanger + 0.25 × Standalone + 0.05 × Rules`

## 5. Running the Project

### Requirements

- Python 3.9 or later.
- Timestamped screenplay `.txt` files.
- An API key for LLM evaluation.

### Rule-Based Execution

Place the screenplay files in a local folder and run:

```bash
python run.py --pack ./pack --out outputs/baseline
```

This runs candidate generation and rule-based evaluation without an API key.

### LLM-Based Execution — Groq

The complete experiment used Groq-hosted Qwen 3.8 27B.

In PowerShell, configure the environment variables:

```powershell
$env:LLM_API_KEY = "YOUR_GROQ_API_KEY"
$env:LLM_BASE_URL = "https://api.groq.com/openai/v1"
```

Run:

```powershell
python run.py --pack "./pack" --out "outputs/llm" --llm --model "qwen/qwen3.8-27b" --sleep 5
```

Replace `./pack` with the location of your screenplay collection.

Never commit API keys or confidential screenplay files to the repository.

### Alternative Models

The LLM client supports OpenAI-compatible endpoints and an Anthropic API option.

Configuration is controlled through:

- `LLM_PROVIDER`
- `LLM_BASE_URL`
- `LLM_MODEL`
- `LLM_API_KEY`

See `promofinder/llm.py` for implementation details.

## 6. Experimental Results

The complete successful LLM run processed all 50 episodes.

| Metric | Groq Qwen 3.8 27B | Rule-Based Baseline |
|---|---:|---:|
| Episodes processed | 50 | 50 |
| Candidate windows | 16,602 | 16,602 |
| Promotional candidates | 74 | 112 |
| Pipeline errors | 0 | 0 |
| Candidates rejected by LLM | 13 | N/A |
| LLM calls | 50 | N/A |
| Approximate input characters | 294,897 | N/A |

The screenplay collection contained 3,727 timestamped events, with zero parser warnings.

The rule-based baseline retained 112 non-overlapping candidates. The LLM-based run produced 74 promotional candidates.

These results demonstrate the use of LLM evaluation as an additional narrative filtering stage. They do not establish that every selected candidate is ready for publication.

## 7. Manual Quality Evaluation

A manual spot-check was conducted on 11 selected promotional clips:

| Evaluation | Count |
|---|---:|
| Pass | 9 |
| Partial | 2 |
| Total reviewed | 11 |

Two observed limitations were:

- Episode 30: The LLM incorrectly described the protagonist as facing or accepting a dangerous trap, although the protagonist was not present in the selected scene.
- Episode 47: The LLM classified a resolved power-reversal scene as a cliffhanger.

Human review remains necessary.

## 8. Limitations

- **Script-only analysis:** The prototype does not inspect actual video, audio, background music, visual composition, subtitles, or editing continuity.
- **Subjective evaluation:** Hook strength and cliffhanger quality can be interpreted differently by an LLM.
- **Context dependency:** Some clips may require information from preceding scenes.
- **No audience-performance validation:** There is no CTR, retention, conversion, or A/B testing data.
- **Limited manual evaluation:** Only 11 of the 74 LLM-selected candidates were manually reviewed.
- **API constraints:** External model usage is subject to rate limits and availability.

## 9. Future Improvements

- Expand manual evaluation to all selected candidates.
- Introduce explicit hook and ending classifications.
- Add context-dependency indicators.
- Compare multiple LLM evaluations for consistency.
- Integrate video and audio analysis.
- Incorporate audience engagement metrics.
- Add caching, parallel episode processing, and API usage monitoring for larger screenplay collections.

## 10. AI Tools and Disclosure

- **Groq-hosted Qwen 3.8 27B:** Used for the complete 50-episode LLM evaluation.
- **Gemini 3.8 Flash:** Tested on three episodes, producing five promotional candidates. A full-run attempt timed out and was not used for the reported results.
- **ChatGPT:** Used for development guidance, debugging assistance, code review, and documentation.

Manual inspection was used to evaluate a sample of generated candidates.

## 11. Conclusion

Promo Finder demonstrates a hybrid AI approach to discovering promotional clips from timestamped microdrama screenplays.

By combining rule-based candidate generation with LLM-based narrative evaluation, the prototype processed 50 episodes and generated 74 ranked promotional candidates without pipeline errors.

It is intended as an AI-assisted editorial discovery tool that reduces manual screenplay review, while retaining human evaluation as an essential part of the final selection process.
