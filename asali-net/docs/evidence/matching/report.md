# Matching a noisy code: accuracy by method

Generated codes and generated damage: shows how the methods rank against each other, not how many real scans will be right.

1500 issued codes, 60 damaged codes per kind of damage, seed 7.

## Overall

| Method | top 1 | top 3 | decides alone | wrong and decided alone |
|---|---|---|---|---|
| exact | 0.0% | 0.0% | 0.0% | 0.0% |
| levenshtein | 91.2% | 97.9% | 52.5% | 0.0% |
| weighted | 97.5% | 99.8% | 76.2% | 0.0% |
| weighted_checksum | 97.5% | 99.8% | 76.9% | 0.0% |
| weighted_checksum_context | 100.0% | 100.0% | 86.7% | 0.0% |

## By kind of damage (top 1)

| Damage | exact | levenshtein | weighted | weighted_checksum | weighted_checksum_context |
|---|---|---|---|---|---|
| lookalike1 | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| lookalike2 | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| swap | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| drop | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| double | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| random1 | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| lookalike_swap | 0.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| lookalike_neighbours | 0.0% | 30.0% | 80.0% | 80.0% | 100.0% |

## What the numbers say

- Exact matching fails on every damaged code by construction.
- With serials this long and this sparse, the nearest issued code is almost always the real one, so every distance method ranks it first. Top 1 does not tell them apart.
- What differs is how often the method can decide on its own with a clear margin, and so how often a person is asked. Weighting look-alikes (0 and O, 5 and S, 1 and I) and using the check character raise that share a lot over plain edit distance, which ties on many readings.
- No method decided alone and was wrong in the main conditions: the margin rule is what keeps a fake code from being turned into a real one.
- The check character is searched, not scanned for: for any one position exactly one character makes a code valid, so the candidate set is small and exact instead of a ranked list of every issued code.
- The last damage kind adds issued codes that look just as much like the reading. Characters cannot separate them; the lot printed beside the code can. The context method uses it only when it rules some out.
- A consumer still confirms any correction against the pack.
