# Demo script, about ten minutes

Run on four computers if possible (see `docs/runbook/FOUR_PCS.md`). On one computer, run `bash infra/scripts/sim_rebuild.sh` and say so:
the screens show "Simulation: all organisations are running on this computer", and that is true.

Staff sign in as `staff` with the password in `infra/out/<PC or SIM>/.env` (or `secrets.json` in the local simulation).

| Minute | Computer and screen | What to do | What the audience should see |
|---|---|---|---|
| 0 | Any, Network page | Open Network on any portal | Twelve organisations, the computer each runs on, three kinds of database, latency from this node |
| 1 | Tarang Pharma (PC-B), Batches | Create a batch, make 10 packs, open Print labels | A label sheet with a QR code and the code in groups of four, in a typeface where 0 and O differ |
| 2 | Tarang Pharma, Dispatch | Choose North Star, type five codes | Each pack appears at once with a sound; a total of five |
| 3 | North Star (PC-C), Receive | Open the shipment; type four codes, one with a swapped character | The swapped one is read as "corrected to" the right code, with Undo. The count says 4 of 5, and finishing names one missing pack |
| 4 | Sharma Medicos (PC-D), Sell | Receive three packs, sell one at a price | Receipt in Hindi (marked as awaiting review) with a QR to the Delhi consumer portal |
| 5 | Consumer Delhi (PC-A) | Type the code with an O where a 0 is printed | "Does your pack show ...?" and nothing else until Yes. Then Genuine, with the route and the computer behind each line |
| 6 | Consumer Delhi | Check the copied code (scenario S3) | Do not use: sold by two shops. Under it, a customer report in another city, labelled as not verified, against the records |
| 7 | Regulator (PC-A), Documents | Paste a quality notice for a Kesar batch, then check one of its packs on the consumer portal | The notice was never entered as an alert, yet the pack now reads Do not use, with the notice quoted and its link confidence shown |
| 8 | Stop one organisation (`docker compose stop dist-west-app`) | Check a pack that went through it | Cannot check, naming the organisation that did not answer. Start it again and the same check is Genuine |
| 9 | Regulator, Complaints | Open it | Complaints grouped by batch, with unusually many flagged |
| 10 | Any, Network | Open it again | The stopped organisation is back online |

If a step fails live, say what failed. Do not retry until it passes without saying so.
