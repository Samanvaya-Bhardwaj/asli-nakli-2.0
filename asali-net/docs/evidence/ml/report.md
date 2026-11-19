Hand-written set: not yet provided

Date 2026-11-19, commit e78da9d, data hash 72abaa912161dcd4
Dataset: 1110 documents; train 749, validation 178, test 183. Test families are not in training.

## Results on the generated test families

| Component | Metric | Result | Target | |
|---|---|---|---|---|
| M1 | m1_macro_f1 | 0.958 | >= 0.9 | met |
| M2 | m2_micro_f1 | 0.661 | >= 0.8 | MISSED |
| CODES | codes_precision | 1.000 | >= 0.98 | met |
| CODES | codes_recall | 0.996 | >= 0.95 | met |
| NAMES | names_precision | 0.987 | >= 0.9 | met |
| NAMES | names_recall | 0.996 | >= 0.85 | met |
| M3 | m3_precision | 1.000 | >= 0.95 | met |
| M3 | m3_recall | 0.903 | >= 0.85 | met |
| M4 | m4_f1 | 1.000 | >= 0.85 | met |
| RETRIEVAL | retrieval_recall_at_10 | 0.914 | >= 0.9 | met |
| RETRIEVAL | retrieval_unrelated_max | 0.000 | <= 1.0 | met |

## Missed targets

- m2_micro_f1: 0.661 against a target of 0.8

## M3 against the baseline (exact code match only)

- M3 at 0.8: precision 1.000, recall 0.903
- Baseline: precision 0.938, recall 0.582
- Links reached through a misread code or a name only (the baseline cannot find these): 0 in the test set, M3 found 0.
- Brier score 0.0170. Reliability chart: m3_reliability.png

## M1 confusion matrix (rows true, columns predicted)

| |ban_order|batch_release_note|coa|consumer_complaint|counter_note|damage_report|delivery_note|deviation_report|discrepancy_note|inspection_report|nsq_alert|recall_notice|return_note|temperature_report|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ban_order | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| batch_release_note | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| coa | 0 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| consumer_complaint | 0 | 0 | 0 | 71 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| counter_note | 0 | 0 | 0 | 9 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| damage_report | 0 | 0 | 0 | 0 | 0 | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| delivery_note | 0 | 0 | 0 | 0 | 0 | 0 | 13 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| deviation_report | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 |
| discrepancy_note | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 |
| inspection_report | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 0 | 0 | 0 | 0 |
| nsq_alert | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 4 | 0 | 0 | 0 |
| recall_notice | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | 0 | 0 |
| return_note | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 6 | 0 |
| temperature_report | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 20 |

## M2 F1 per label

- suspected_fake: 0.606
- packaging_different: 0.629
- no_effect: 0.519
- side_effect: 0.737
- expired_or_near_expiry: 0.846
- overcharged: 0.950
- damaged_pack: 0.476
- wrong_medicine: 0.412
- other: 0.000

## Mentions (precision, recall)

- serial: 1.000, 0.987
- lot: 1.000, 1.000
- shipment_ref: 1.000, 1.000
- product: 0.993, 0.993
- org: 0.968, 0.995
- city: 1.000, 1.000

## M4 duplicates and retrieval

- M4 threshold 0.9 (from validation), F1 1.000.
- Retrieval over 96 queries: recall@10 0.914, unrelated documents in the top 10 0.00 on average.
