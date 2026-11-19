"""Sentence plans for every document type. Six families per type: each family is its own sentence structure
and wording, so the test family (5) and validation family (4) contain phrasing training never saw.

Placeholders are filled by generate_corpus.py. {code} is the pack's code as the author wrote it.
"""

FAMILIES = 6
TRAIN, VAL, TEST = (0, 1, 2, 3), (4,), (5,)

FRAMES: dict[str, list[str]] = {
    "coa": [
        "Certificate of analysis\nProduct: {product} {strength}\nBatch: {lot}\nMfg {mfg}  Exp {expiry}\nAssay {assay}%  Dissolution {dissolution}% at 30 min\n{result}\nReleased by QA {qa}, {maker}",
        "{maker} quality control. COA for {product} {strength}, lot {lot}, made {mfg}, expires {expiry}. Tests: assay {assay}%, dissolution {dissolution}%. {result}",
        "CERTIFICATE OF ANALYSIS - {maker}\nItem {product} ({strength})  B.No. {lot}\nManufactured {mfg}; use before {expiry}\nResults: assay {assay}, dissolution {dissolution}.\nConclusion: {result}\nSigned {qa}",
        "Batch {lot} of {product} {strength} was tested at {maker}. Assay came to {assay}% and dissolution to {dissolution}%. {result} Mfd {mfg}, expiry {expiry}. QA {qa}.",
        "Analytical report | {product} {strength} | lot {lot}\nMade {mfg} | Expiry {expiry}\nAssay {assay}% | Dissolution {dissolution}%\nOutcome: {result} ({qa}, {maker})",
        "We have tested lot {lot} ({product}, {strength}) for {maker}: assay {assay}%, dissolution {dissolution}% in 30 minutes. {result} Manufacturing date {mfg}, expiry {expiry}. Approved by {qa}.",
    ],
    "batch_release_note": [
        "Batch release note. {maker} releases lot {lot} of {product} {strength} to market. Quantity {qty} packs. Released {date} by {qa}.",
        "RELEASE: {product} {strength}, B.No. {lot}, {qty} packs cleared for sale on {date}. QA: {qa}. {maker}",
        "On {date} {qa} signed off batch {lot} ({product} {strength}) for distribution. {qty} packs. Issued by {maker}.",
        "{maker} - market release\nLot {lot}\n{product} {strength}\nPacks {qty}\nDate {date}\nApproved {qa}",
        "Lot {lot} of {product} {strength} is released to the market, {qty} packs, per QA {qa} on {date} ({maker}).",
        "This note confirms {maker} cleared {qty} packs of {product} {strength} (batch {lot}) for dispatch. Date {date}. Name {qa}.",
    ],
    "deviation_report": [
        "Deviation report. During manufacture of {product} {strength}, batch {lot}, {issue}. Impact: {impact}. Action: {action}. {maker}.",
        "{maker} DEVIATION NOTICE\nBatch {lot} ({product})\nWhat happened: {issue}\nImpact on quality: {impact}\nCorrective action: {action}",
        "While making lot {lot} of {product} {strength} we found that {issue}. We assessed the effect as: {impact}. We then {action}. - {maker}",
        "Deviation | {lot} | {product} {strength}\n{issue}\nAssessment: {impact}\nDecision: {action}\nRaised by {maker}",
        "QA record for {maker}: for {product}, lot {lot}, {issue}. The batch impact was judged {impact}; {action}.",
        "Report of a manufacturing deviation on {product} {strength} (B.No. {lot}): {issue}. Impact {impact}. Follow-up: {action}. {maker}",
    ],
    "recall_notice": [
        "RECALL NOTICE\n{maker} is recalling {product} {strength}, lot {lot}.\nReason: {reason}.\nLevel: {level}.\nShops should stop selling this lot and return stock. Patients should not take it.",
        "{maker} recall of {product} {strength}. Affected batch: {lot}. Why: {reason} ({level}). Stop sale now and return all packs.",
        "Notice to shops and distributors: lot {lot} of {product} {strength} made by {maker} is recalled because {reason}. Recall {level}. Do not sell. Do not use.",
        "Product recall - {level}\n{product} {strength} | B.No. {lot} | {maker}\nReason: {reason}\nAction: quarantine, return to {maker}",
        "We, {maker}, are withdrawing batch {lot} of {product} {strength} from the market ({reason}). This is a {level} recall. Patients should not use remaining packs.",
        "Withdrawal of {product} {strength} lot {lot} by {maker}: {reason}. Classification {level}. Please stop supply and send stock back.",
    ],
    "temperature_report": [
        "Shipment {ref} ({from_org} to {to_org}). Logger {logger}.\n{readings}\n{narrative}",
        "Cold chain log for {ref}, {from_org} to {to_org}, logger {logger}:\n{readings}\nSummary: {narrative}",
        "TEMPERATURE REPORT {ref}\nFrom {from_org}, to {to_org}\nData logger {logger}\n{readings}\nRemarks: {narrative}",
        "{from_org} dispatched shipment {ref} to {to_org}. The logger ({logger}) recorded:\n{readings}\n{narrative}",
        "Logger {logger} / consignment {ref} / {from_org} -> {to_org}\n{readings}\nNote: {narrative}",
        "Transit temperature record, {ref}. Route {from_org} to {to_org}. Device {logger}.\n{readings}\nOutcome: {narrative}",
    ],
    "delivery_note": [
        "Delivery note {ref}. {from_org} to {to_org}. {cartons} cartons, vehicle {vehicle}. {remarks}",
        "DELIVERY {ref}\nFrom: {from_org}\nTo: {to_org}\nCartons: {cartons}  Vehicle: {vehicle}\n{remarks}",
        "Consignment {ref} left {from_org} for {to_org} in vehicle {vehicle} with {cartons} cartons. {remarks}",
        "{from_org} -> {to_org} | {ref} | {cartons} cartons | {vehicle}\nRemarks: {remarks}",
        "Goods dispatched under {ref}: {cartons} cartons by truck {vehicle}, {from_org} to {to_org}. {remarks}",
        "We delivered {cartons} cartons on {ref} ({vehicle}) from {from_org} to {to_org}. {remarks}",
    ],
    "discrepancy_note": [
        "Discrepancy note. Shipment {ref}: expected {expected}, received {received}. Missing packs: {missing}. Recorded by {org}.",
        "{org} - RECEIVING DISCREPANCY\nRef {ref}\nExpected {expected}\nReceived {received}\nNot received: {missing}",
        "On receiving {ref} we counted {received} packs against {expected} expected. The following were missing: {missing}. {org}",
        "Short delivery on {ref}: expected {expected}, received {received}. Missing codes {missing} ({org}).",
        "Count mismatch for consignment {ref} at {org}. Expected {expected} / received {received}. Missing: {missing}",
        "{org} reports that shipment {ref} arrived with {received} of {expected} packs. Missing serials: {missing}.",
    ],
    "damage_report": [
        "Damage report for {ref}. {damage} Reported by {org}.",
        "{org} DAMAGE REPORT\nShipment {ref}\n{damage}",
        "When shipment {ref} reached {org}, {damage}",
        "Shipment {ref} / {org} / damage: {damage}",
        "At {org}, consignment {ref} was found damaged. {damage}",
        "Report from {org} on {ref}: {damage}",
    ],
    "counter_note": [
        "Counter note {date}. {shop}, {city}. Customer says {claim} Product {product}. {codes}",
        "{shop} ({city}) - note from the counter. A customer came back on {date} and said {claim} {codes} ({product})",
        "Staff note, {date}: customer complained that {claim} Pack: {product}. {codes} Shop {shop}.",
        "{date} / {city} / {shop}\nCustomer feedback: {claim}\n{product} {codes}",
        "Noting down what a customer told us at {shop}, {city}: {claim} It was {product}. {codes} ({date})",
        "Complaint received over the counter at {shop} on {date}. {claim} {product}. {codes}",
    ],
    "return_note": [
        "Return note. Bill {bill}. {codes} {product} returned at {shop}. Reason: {reason}.",
        "{shop} RETURN\nBill no {bill}\nItem {product}  {codes}\nReason for return: {reason}",
        "A pack of {product} sold on bill {bill} came back to {shop}. {codes} The customer said {reason}.",
        "Returned: {product} / {codes} / bill {bill} / {shop} / {reason}",
        "{shop} took back {product} ({codes}) against bill {bill}. Reason given: {reason}.",
        "Return recorded for bill {bill}: {product}, {codes}. Why: {reason}. {shop}.",
    ],
    "consumer_complaint": [
        "{opening} {body} {codes} {closing}",
        "{body} {codes} {opening} {closing}",
        "{opening}\n{body}\n{codes}\n{closing}",
        "{codes} {opening} {body} {closing}",
        "{body} {opening} {codes} {closing}",
        "{opening} {codes} {body} {closing}",
    ],
    "nsq_alert": [
        "Drugs declared not of standard quality, {month}.\n{rows}",
        "NSQ ALERT - {month}\nThe following batches failed testing:\n{rows}",
        "Monthly list of not of standard quality drugs for {month}:\n{rows}\nStop sale and return stock.",
        "Not of standard quality ({month})\n{rows}\nIssued by the drug controller.",
        "Drug control NSQ statement, {month}. Batches found below standard:\n{rows}",
        "{month}: batches reported as NSQ\n{rows}\nDistributors and shops must withdraw these.",
    ],
    "ban_order": [
        "Order banning {product} lot {lot}. Reason: {reason}. Effective {date}.",
        "BAN ORDER\nProduct: {product} {strength}\nBatch: {lot}\nGround: {reason}\nDate: {date}",
        "The drug controller bans sale of {product} (B.No. {lot}) from {date} because {reason}.",
        "Prohibition notice {date}: {product} {strength}, lot {lot}. Legal reason: {reason}.",
        "With effect from {date}, lot {lot} of {product} may not be sold. Reason: {reason}.",
        "Banned: {product} / {lot} / {date} / {reason}",
    ],
    "inspection_report": [
        "Inspection report. {org}, {city}, {date}. {findings} Outcome: {outcome}.",
        "INSPECTION - {org} ({city})\nDate {date}\nFindings: {findings}\nOutcome: {outcome}",
        "On {date} the inspector visited {org} in {city}. {findings} The result was: {outcome}.",
        "{date} | {org} | {city}\n{findings}\nConclusion: {outcome}",
        "Visit to {org}, {city}, on {date}: {findings} Overall {outcome}.",
        "Drug inspector's note for {org} ({date}, {city}). {findings} Result {outcome}.",
    ],
}  # fmt: skip

# complaint sentences: label -> six English variants (one per family), plus Hinglish variants shared by all families
ISSUE_EN: dict[str, list[str]] = {
    "suspected_fake": [
        "I think this pack is fake.", "This does not look like a genuine pack to me.", "The medicine seems to be counterfeit.",
        "I am sure this is a duplicate, not the real thing.", "Something is wrong, this feels like a fake strip.", "Please check, I believe the pack is not original.",
    ],
    "packaging_different": [
        "The strip colour is different from last time.", "The packaging looks changed compared to my earlier purchase.", "The printing on the box is not the same as before.",
        "Foil and box design are different from what I always buy.", "The wrapper looks unlike the usual one.", "Box colour and font do not match my previous pack.",
    ],
    "no_effect": [
        "It had no effect at all.", "The medicine did not help me.", "I took the full course and nothing improved.",
        "There was no benefit from these tablets.", "My condition stayed exactly the same after taking it.", "It does not work like the earlier ones did.",
    ],
    "side_effect": [
        "It gave me a rash and nausea.", "I felt dizzy and sick after the first dose.", "Since taking it I have had a headache and stomach pain.",
        "I had an allergic reaction after one tablet.", "It made me vomit twice.", "I developed itching and swelling after taking it.",
    ],
    "expired_or_near_expiry": [
        "The expiry is very close.", "It was sold to me with only a month left.", "The pack was already expired when I opened it.",
        "Expiry date is almost over.", "The shop gave me a pack that is about to expire.", "It expires next month, which was not told to me.",
    ],
    "overcharged": [
        "The shop charged more than the printed price.", "I was billed above MRP.", "They took extra money for this strip.",
        "The price on the bill is higher than on the pack.", "I paid more than the maximum retail price.", "The shopkeeper asked for more than MRP.",
    ],
    "damaged_pack": [
        "The pack was torn when I got it.", "The seal was broken.", "Tablets were crushed inside the strip.",
        "The box was crushed and open.", "Some blisters were empty.", "The bottle was leaking.",
    ],
    "wrong_medicine": [
        "I was given a different medicine than the one prescribed.", "The shop handed me the wrong tablets.", "This is not the medicine my doctor wrote.",
        "The strength is not what I asked for.", "They gave me another brand without telling me.", "The name on the strip is not what I ordered.",
    ],
    "other": [
        "I want to report a problem.", "Please look into this.", "Sharing this for your records.", "Telling you in case it helps.", "Flagging this to the authority.", "This needs a look.",
    ],
}  # fmt: skip
ISSUE_HI: dict[str, list[str]] = {
    "suspected_fake": ["Mujhe lagta hai yeh nakli hai.", "Yeh pack asli nahi lag raha.", "Dawai duplicate lagti hai."],
    "packaging_different": ["Strip ka colour pichli baar se alag hai.", "Packing pehle jaisi nahi hai.", "Dabbe ka design badla hua hai."],
    "no_effect": ["Dawai se koi fayda nahi hua.", "Isse mujhe kuch asar nahi hua.", "Goli khane ke baad bhi wahi haal hai."],
    "side_effect": ["Dawai lene ke baad ulti aur chakkar aaye.", "Mujhe rash ho gaya.", "Pet mein dard hone laga."],
    "expired_or_near_expiry": ["Expiry bahut nazdeek hai.", "Pack ki expiry khatam hone wali hai.", "Dukan wale ne purani dawai di."],
    "overcharged": ["Dukan wale ne MRP se jyada paise liye.", "Bill mein jyada rate hai.", "Extra paise maange."],
    "damaged_pack": ["Pack phata hua tha.", "Seal toota hua tha.", "Goliyan tooti hui thi."],
    "wrong_medicine": ["Mujhe doosri dawai de di.", "Yeh woh dawai nahi hai jo likhi thi.", "Strength alag hai."],
    "other": ["Ek problem batana tha.", "Dekh lijiye please.", "Aapko batana zaroori tha."],
}  # fmt: skip
OPENING_EN = ["Hello.", "To whom it may concern,", "Hi team,", "I need to complain.", "Writing about a purchase.", "Sir,"]
CLOSING_EN = ["Please act on this.", "Thank you.", "Kindly look into it.", "I hope this gets checked.", "Regards.", "Waiting for a reply."]
OPENING_HI = ["Namaste.", "Sir,", "Hello team,", "Ek shikayat hai."]
CLOSING_HI = ["Please dekh lijiye.", "Dhanyavad.", "Kuch kijiye.", "Jawab ka intezar hai."]
BUY_EN = ["I bought {product} on {date} from {shop} in {city}.", "On {date} I purchased {product} at {shop}, {city}.", "Picked up {product} from {shop} ({city}) around {date}."]
BUY_HI = ["Maine {date} ko {shop} {city} se {product} liya.", "{date} ko {city} ke {shop} se {product} kharida.", "{product} {shop} se liya tha, {date} ko."]
EXTRA_SENTENCES = ["The weather was bad that day.", "My neighbour also takes the same tablets.", "I have been a customer for years.", "The queue at the shop was long."]

COMPLAINT_REASONS_RETURN = ["strip looks different", "customer says no effect", "broken seal", "wrong strength supplied", "customer changed mind"]
NARRATIVES_NORMAL = ["Temperature stayed within range. Cartons delivered.", "No excursion recorded.", "All readings within limit. Delivered intact."]
NARRATIVES_EXCURSION = ["Reefer unit failed near {place}. Temperature above {limit} C for about {dur}. Cartons delivered.", "Cooling stopped for {dur} on the way. Readings exceeded {limit} C.", "Compressor fault: above {limit} C for roughly {dur}. Delivered."]
DAMAGE_TEXT = ["Two cartons were crushed.", "One carton was wet from rain.", "Seals on three cartons were broken.", "A pallet tilted and cartons were dented."]
DEVIATIONS = [("the granulation moisture was above the limit", "minor", "the batch was retested and passed"), ("a mixer stopped for 40 minutes", "no impact on quality", "the step was repeated"), ("the tablet hardness drifted", "under assessment", "the batch was held")]
RECALL_REASONS = ["failed dissolution test", "out of specification assay result", "foreign particles found", "mislabelled strength", "microbial contamination"]
BAN_REASONS = ["the batch is spurious", "the drug is not of standard quality and unsafe", "the label carries false information"]
INSPECTION_FINDINGS = [("Records and storage are in order.", "satisfactory"), ("Three observations were noted on record keeping.", "observations"), ("Cold storage was not maintained. The licence is suspended.", "licence_action")]
