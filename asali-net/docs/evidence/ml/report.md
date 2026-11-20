Hand-written set: not yet provided

Date 2026-11-20, commit 3b815d3, data hash 2810be4764963ccd
Dataset: 1113 documents; train 751, validation 180, test 182. Test families are not in training.

## Results on the generated test families

| Component | Metric | Result | Target | |
|---|---|---|---|---|
| M1 | m1_macro_f1 | 0.942 | >= 0.9 | met |
| M2 | m2_micro_f1 | 0.653 | >= 0.8 | MISSED |
| CODES | codes_precision | 1.000 | >= 0.98 | met |
| CODES | codes_recall | 1.000 | >= 0.95 | met |
| NAMES | names_precision | 0.983 | >= 0.9 | met |
| NAMES | names_recall | 1.000 | >= 0.85 | met |
| M3 | m3_precision | 1.000 | >= 0.95 | met |
| M3 | m3_recall | 0.906 | >= 0.85 | met |
| M4 | m4_f1 | 0.889 | >= 0.85 | met |
| RETRIEVAL | retrieval_recall_at_10 | 0.986 | >= 0.9 | met |
| RETRIEVAL | retrieval_unrelated_max | 0.000 | <= 1.0 | met |

## Missed targets

- m2_micro_f1: 0.653 against a target of 0.8

## M3 against the baseline (exact code match only)

- M3 at 0.8: precision 1.000, recall 0.906
- Baseline: precision 0.942, recall 0.573
- Links reached through a misread code or a name only (the baseline cannot find these): 2 in the test set, M3 found 1.
- Brier score 0.0178. Reliability chart: m3_reliability.png

## M1 confusion matrix (rows true, columns predicted)

| |ban_order|batch_release_note|coa|consumer_complaint|counter_note|damage_report|delivery_note|deviation_report|discrepancy_note|inspection_report|nsq_alert|recall_notice|return_note|temperature_report|
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ban_order | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| batch_release_note | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| coa | 0 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| consumer_complaint | 0 | 0 | 0 | 70 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| counter_note | 0 | 0 | 0 | 11 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
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

- suspected_fake: 0.607
- packaging_different: 0.755
- no_effect: 0.364
- side_effect: 0.897
- expired_or_near_expiry: 0.872
- overcharged: 0.952
- damaged_pack: 0.311
- wrong_medicine: 0.552
- other: 0.000

## Mentions (precision, recall)

- serial: 1.000, 1.000
- lot: 1.000, 1.000
- shipment_ref: 1.000, 1.000
- product: 0.986, 1.000
- org: 0.963, 1.000
- city: 1.000, 1.000

## M4 duplicates and retrieval

- M4 threshold 0.72 (from validation), F1 0.889.
- Retrieval over 79 queries: recall@10 0.986, unrelated documents in the top 10 0.00 on average.
