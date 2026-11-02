# Research Evaluation

The canonical research workflow eval is `eval/research_eval.py`.

## Commands

```bash
make eval-research
make eval-research-live
make eval-research-gate
```

## Dataset

- `eval/research_golden_set.jsonl`

## Report Schema

Current schema: `report_schema_version=4`.

The report includes:

- `mean_recall_at_k`
- `mean_mrr_at_k`
- `failure_stage_counts`
- per-query `hit_ranks`
- per-query `failure_stage`
