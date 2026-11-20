# Round 18 — context-aware unstructured retrieval and integration (prompt P3-4)

The prompt, quoted exactly as typed. It is titled "Requirement 3"; it implements the assignment's Requirement 4 (search unstructured data with the discovered context and integrate it), as PHASE3_IMPLEMENTATION_PLAN.md numbers them.

> Implement Phase 3 Requirement 3: Context-aware unstructured data retrieval and integration.
>
> OBJECTIVE: Use the overall query context accumulated from all four databases to search unstructured documents and retrieve information that is highly relevant to the original user query. The system must integrate structured query results with relevant unstructured information.
>
> STEP 1: UNSTRUCTURED DATASET — Inspect the existing repository for unstructured datasets. If suitable datasets do not exist, create realistic sample documents related to the Asali/Nakali medicine verification domain. Include documents such as: Manufacturer quality reports. Batch inspection reports. Medicine recall notices. Pharmacy incident reports. Distributor shipment notes. Consumer complaints. Regulatory investigation reports. Product safety documents. Store documents independently from the four structured databases. Do not insert the complete document contents into the structured database tables.
>
> STEP 2: DOCUMENT PROCESSING — Implement a document ingestion pipeline. For each document: 1. Extract its text. 2. Clean and normalize the text. 3. Split long documents into meaningful chunks. 4. Preserve document metadata. 5. Extract relevant entities and identifiers. 6. Make the document searchable. Maintain metadata such as: Document ID. Document title. Document type. Medicine ID. Batch ID. Manufacturer ID. Date. Source. Relevant text or chunk.
>
> STEP 3: CONTEXT-AWARE SEARCH — Use the aggregated context produced by the SCORE-based context discovery module. Construct a search query using: Original user query. Top-ranked context terms. Medicine identifiers. Batch identifiers. Manufacturer information. Relevant contextual attributes. Related entities discovered through FK-PK relationships. Search the unstructured document collection using the existing retrieval technology if available. If no suitable retrieval system exists, implement an appropriate searchable index. Use a relevance-ranking approach such as BM25 or a hybrid retrieval approach where justified. Do not simply search using the original user query. The discovered context must influence document retrieval.
>
> STEP 4: RELEVANCE FILTERING — Rank retrieved documents according to their relevance to the overall query context. Consider: Matching medicine identifiers. Matching batch identifiers. Related manufacturers. Related distributors. Contextual term relevance. Document type. Document date. Avoid retrieving documents merely because they share a common word.
>
> STEP 5: STRUCTURED + UNSTRUCTURED INTEGRATION — Extend the existing mediator to produce a unified response containing: A. Original user query. B. Federated structured query results. C. Local context from each database. D. Aggregated query context. E. Retrieved unstructured documents. F. Document relevance scores. G. Source provenance. H. Explanation of why each document was retrieved. Connect unstructured documents to relevant structured entities wherever reliable identifiers or relationships are available. Preserve the distinction between verified structured facts and information reported in unstructured documents. Do not treat an unverified complaint as proof of counterfeit medicine.
>
> STEP 6: FINAL OUTPUT — Return an explainable integrated result. For example, if the user asks: "Find information about batch BATCH-101 manufactured by ABC Pharma and identify any quality or safety concerns." The system should: 1. Query relevant structured databases. 2. Discover additional context through FK-PK relationships. 3. Identify related manufacturer, distributor, shipment, quality and regulatory information. 4. Aggregate the discovered context. 5. Search relevant unstructured reports and complaints. 6. Return the structured results and related documents. Display the retrieved documents with their titles, sources, relevance scores and matching context.
>
> IMPORTANT: Use actual unstructured documents, not hardcoded search responses. Do not return the same documents for every query. Ensure that changing the user query changes the context and document retrieval results. Preserve source provenance. Do not replace the existing medicine verification engine.
>
> TESTING: Test at least three different user queries. Show: 1. Original query. 2. Aggregated context. 3. Search query generated from that context. 4. Retrieved documents. 5. Relevance ranking. 6. Final integrated response. Document the complete retrieval pipeline.

The example's BATCH-101 and ABC Pharma do not exist in this data. The demonstration uses the real BATCH-A009 by Biocon.

`generated/` holds the files in FILES.txt as they stood before the first end-to-end run. It was taken after three fixes made while building the corpus (CHANGES_PHASE3.md item 14). As in round 17, the files this round modified were not snapshotted separately before it started.
