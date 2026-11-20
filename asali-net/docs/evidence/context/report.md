# Context discovered across organisations

Run 2026-11-20 12:44. Simulation on one computer; generated corpus.

30 packs checked. On average 3.13 organisations found context and 9.13 foreign-key joins were followed per pack, over mongo, postgres, sqlite.

## Does the context find documents about the pack's product?

- Documents found by the context: 1.87 per pack, 0.732 of them name the pack's product or its generic name.
- Documents found by the question's words alone: 5.0 per pack, 0.2 of them name the product.

The comparison is on generated documents and generated packs. It shows what the context adds, not how real documents would behave.

## Scenario packs

### S1: genuine, Pantotar (pantoprazole)

4 of 6 organisations found context.

- tarang: explored units, shipment_units, products, batches, shipments; followed units(gtin) -> products(gtin); units(lot) -> batches(lot); shipment_units(shipment_id) -> shipments(shipment_id)
- dist-north: explored receipt_items, dispatch_items, dispatches, receipts, parties; followed dispatch_items(dispatch_id) -> dispatches(dispatch_id); receipt_items(receipt_id) -> receipts(receipt_id); dispatches(to_org_id) -> parties(org_id)
- shop-delhi: explored purchase_items, sale_items, purchases, parties, sales; followed purchase_items(pur_id) -> purchases(pur_id); purchases(distributor_org) -> parties(org_id); sale_items(bill_no) -> sales(bill_no)
- consumer-delhi: explored checks, verdicts, cities; followed checks(verdict) -> verdicts(verdict); checks(city) -> cities(city)
- consumer-mumbai: explored nothing
- regulator: explored nothing

Strongest terms: DSP-7032f207be (dist-north, shop-delhi); SHP-e951a48044 (dist-north, tarang); brand_name=Pantotar (tarang); generic_name=pantoprazole (tarang); dist-north (shop-delhi, tarang)

### S3: do_not_use, Azivra (azithromycin)

4 of 6 organisations found context.

- medivra: explored lots, skus, consignmentLines, consignments, parties; followed lots(sku) -> skus(_id); lots(_id) -> consignmentLines(lot); consignmentLines(consignment) -> consignments(_id); consignments(consignee) -> parties(_id)
- dist-north: explored receipt_items, dispatch_items, dispatches, receipts, parties; followed dispatch_items(dispatch_id) -> dispatches(dispatch_id); receipt_items(receipt_id) -> receipts(receipt_id); dispatches(to_org_id) -> parties(org_id)
- shop-delhi: explored purchase_items, sale_items, purchases, parties, sales; followed purchase_items(pur_id) -> purchases(pur_id); purchases(distributor_org) -> parties(org_id); sale_items(bill_no) -> sales(bill_no)
- consumer-delhi: explored checks, verdicts, cities, check_reasons; followed checks(verdict) -> verdicts(verdict); checks(city) -> cities(city); checks(check_id) -> check_reasons(check_id)
- consumer-mumbai: explored nothing
- regulator: explored nothing

Strongest terms: DSP-7032f207be (dist-north, shop-delhi); brand=Azivra (medivra); molecule=azithromycin (medivra); SHP-dfcfef4811 (dist-north, medivra); B-86020348da (shop-delhi)

### S7: caution, Glargikes (insulin glargine)

3 of 5 organisations found context.

- kesar: explored SRL_MST, DSP_DTL, LOT_MST, ITEM_MST, DSP_HDR, PARTY_MST; followed SRL_MST(LOT_NO) -> LOT_MST(LOT_NO); LOT_MST(ITEM_CD) -> ITEM_MST(ITEM_CD); DSP_DTL(DSP_NO) -> DSP_HDR(DSP_NO); DSP_HDR(PARTY_CD) -> PARTY_MST(PARTY_CD)
- dist-north: explored receipt_items, receipts, parties; followed receipt_items(receipt_id) -> receipts(receipt_id); receipts(from_org_id) -> parties(org_id)
- consumer-delhi: explored checks, verdicts, cities, check_reasons; followed checks(verdict) -> verdicts(verdict); checks(city) -> cities(city); checks(check_id) -> check_reasons(check_id)
- consumer-mumbai: explored nothing
- regulator: explored nothing

Strongest terms: SHP-eef035dd1e (dist-north, kesar); ITEM_DESC=Glargikes (kesar); MOL_DESC=insulin glargine (kesar); Delhi (consumer-delhi); RCP8224d5606e (dist-north)

### S5: do_not_use, Cetivra (cetirizine)

4 of 6 organisations found context.

- medivra: explored lots, skus, consignmentLines, consignments, parties; followed lots(sku) -> skus(_id); lots(_id) -> consignmentLines(lot); consignmentLines(consignment) -> consignments(_id); consignments(consignee) -> parties(_id)
- dist-north: explored receipt_items, dispatch_items, dispatches, receipts, parties; followed dispatch_items(dispatch_id) -> dispatches(dispatch_id); receipt_items(receipt_id) -> receipts(receipt_id); dispatches(to_org_id) -> parties(org_id)
- shop-delhi: explored purchase_items, sale_items, purchases, parties, sales; followed purchase_items(pur_id) -> purchases(pur_id); purchases(distributor_org) -> parties(org_id); sale_items(bill_no) -> sales(bill_no)
- consumer-delhi: explored checks, verdicts, cities, check_reasons; followed checks(verdict) -> verdicts(verdict); checks(city) -> cities(city); checks(check_id) -> check_reasons(check_id)
- consumer-mumbai: explored nothing
- regulator: explored nothing

Strongest terms: DSP-7032f207be (dist-north, shop-delhi); QUALITY_FAILED (consumer-delhi); brand=Cetivra (medivra); molecule=cetirizine (medivra); SHP-dc598a2f2b (dist-north, medivra)

### S6: caution, Glargikes (insulin glargine)

4 of 6 organisations found context.

- kesar: explored SRL_MST, DSP_DTL, LOT_MST, ITEM_MST, DSP_HDR, PARTY_MST; followed SRL_MST(LOT_NO) -> LOT_MST(LOT_NO); LOT_MST(ITEM_CD) -> ITEM_MST(ITEM_CD); DSP_DTL(DSP_NO) -> DSP_HDR(DSP_NO); DSP_HDR(PARTY_CD) -> PARTY_MST(PARTY_CD)
- dist-north: explored receipt_items, dispatch_items, dispatches, receipts, parties; followed dispatch_items(dispatch_id) -> dispatches(dispatch_id); receipt_items(receipt_id) -> receipts(receipt_id); dispatches(to_org_id) -> parties(org_id)
- shop-delhi: explored purchase_items, sale_items, purchases, parties, sales; followed purchase_items(pur_id) -> purchases(pur_id); purchases(distributor_org) -> parties(org_id); sale_items(bill_no) -> sales(bill_no)
- consumer-delhi: explored checks, verdicts, cities, check_reasons; followed checks(verdict) -> verdicts(verdict); checks(city) -> cities(city); checks(check_id) -> check_reasons(check_id)
- consumer-mumbai: explored nothing
- regulator: explored nothing

Strongest terms: DSP-7032f207be (dist-north, shop-delhi); SHP-eef035dd1e (dist-north, kesar); COLD_CHAIN (consumer-delhi); ITEM_DESC=Glargikes (kesar); MOL_DESC=insulin glargine (kesar)

