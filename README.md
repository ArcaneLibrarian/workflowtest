# workflowtest

This repo includes a reusable GitHub Actions workflow to generate summary statistics and a Benford's Law analysis from the journal entry Excel export (`je_samples (1).xlsx`). The workflow writes outputs to an `outputs/` folder and uploads the folder as a workflow artifact so you can download the results.

## How it works

- The analysis script lives at `scripts/analyze_je.py` and includes Benford's Law checks on numeric columns.
- GitHub Actions runs the script on demand (manual trigger) or when the inputs change.
- Outputs are stored in `outputs/` and uploaded as the `je-analysis-outputs` artifact.

## Running locally

```bash
python -m pip install -r requirements.txt
python scripts/analyze_je.py --input "je_samples (1).xlsx" --output outputs
```

## Output files

The script generates:

- `summary.json`: machine-readable summary per sheet
- `summary.md`: human-readable summary (row counts, date ranges, numeric summaries)
- `column_stats.csv`: per-column counts, nulls, and unique values
- `describe_<sheet>.csv`: pandas `describe()` output per sheet
- `benford_summary.csv`: Benford's Law leading digit distribution and chi-square per numeric column

## Running in GitHub Actions

1. Go to **Actions → Journal Entry Analysis**.
2. Click **Run workflow**.
3. Download the `je-analysis-outputs` artifact from the run summary.
