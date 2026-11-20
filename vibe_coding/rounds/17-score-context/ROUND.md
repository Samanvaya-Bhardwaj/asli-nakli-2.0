# Round 17 — SCORE-inspired query context discovery (prompt P3-3)

The prompt, quoted exactly as typed. It is titled "Requirement 2", but it implements the assignment's Requirement 3 (accumulating relevant query context) and the context half of Requirement 2, as PHASE3_IMPLEMENTATION_PLAN.md numbers them.

> Implement Phase 3 Requirement 2: SCORE-inspired query context discovery using FK-PK relationships.
>
> OBJECTIVE: Every database must independently discover additional context related to the user's query by exploring its local database schema and neighbouring tables.
>
> REFERENCE: Follow the SCORE approach discussed in Week-11 L1 SCORE.
>
> CORE CONCEPT: Given a user query Q: 1. Execute the corresponding structured SQL subquery. 2. Obtain its result relation. 3. Extract relevant terms from the query results. 4. Look beyond the original query by exploring neighbouring tables connected through foreign-key relationships. 5. Select relevant FK-based joins. 6. Extract additional context from the joined records. 7. Return a ranked set of context terms.
>
> IMPLEMENTATION:
> STEP 1: QUERY RESULT ANALYSIS — For each database: Receive its assigned SQL subquery. Execute it locally. Retain all relevant columns, including columns not present in the final projection if they are needed for context. Identify the tables and attributes involved.
> STEP 2: SCHEMA RELATIONSHIP DISCOVERY — Inspect the database schema and identify: Primary keys. Foreign keys. Referenced tables. Referenced columns. Relationships between neighbouring tables. Represent the schema as a graph where tables are nodes and FK-PK relationships are edges.
> STEP 3: CONTEXT EXTRACTION — Extract candidate terms from the original query results. Support: Text-valued attributes. Numeric attributes. Categorical attributes. Identifiers. Dates and relevant business attributes. Assign relevance weights to candidate terms. Use term frequency or another appropriate term-weighting approach, keeping the original SCORE-inspired ranking logic.
> STEP 4: NEIGHBOURING TABLE EXPLORATION — Implement iterative FK-PK exploration. For each candidate foreign key: 1. Identify the referenced primary-key table. 2. Perform the corresponding join. 3. Examine the additional records. 4. Extract relevant terms. 5. Calculate the relevance of the FK column. 6. Prioritize the most relevant FK relationship. 7. Continue exploring relevant neighbouring tables. Implement a configurable MAX_AUGMENTATION limit to prevent uncontrolled expansion. Implement a configurable TOP_N parameter to control the number of context terms returned. Avoid exploring unrelated tables simply because a foreign-key relationship exists.
> STEP 5: CONTEXT RANKING — Rank context terms based on their relevance to the original user query. The resulting context should include: Term/value. Source database. Source table. Source column. Relevance score. Relationship path. Associated entity identifiers. Preserve provenance for every extracted term.
> STEP 6: DATABASE-LOCAL CONTEXT — Each database must execute its own context discovery algorithm using its local schema and records. Return a structured response containing: Original subquery. Query result. Explored tables. FK-PK relationships followed. Additional records discovered. Extracted context terms. Relevance scores. Final ranked local context.
> STEP 7: CONTEXT AGGREGATION — Extend the existing mediator to collect the local contexts returned by all four databases. Combine them into one overall query context. Deduplicate repeated terms while preserving their source provenance. Rank the accumulated terms according to relevance to the original user query.
>
> IMPORTANT: Follow SCORE's query-context and neighbouring-table exploration concepts. Use actual FK-PK relationships, not manually hardcoded table traversal. Do not explore every table indiscriminately. Do not replace the existing GAV architecture. Do not confuse entity matching with query context discovery. Do not perform all context discovery only at the coordinator. Keep the implementation configurable and reusable.
>
> TESTING: Use at least three different medicine-related queries. Demonstrate: 1. Initial SQL results. 2. Additional tables explored. 3. FK-PK joins performed. 4. Context terms extracted. 5. Local context returned by each database. 6. Final aggregated context. 7. Why the discovered context is relevant to the query. Document the algorithm and its execution flow.

`generated/` holds the files listed in FILES.txt as they stood before the full pipeline ran. It was taken *after* the first single-database smoke test, whose fix is CHANGES_PHASE3.md item 9.

The "before" state of the files this round modified is their P3-2 state: `generated_v0_phase3/` plus the P3-2 changes (items 3–8). That state was not snapshotted separately, which is a gap in this record.
