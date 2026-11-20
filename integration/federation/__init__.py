"""
Phase 3: federated, context-aware integration.

Requirement 1 (this package so far):
  schema_catalog  - reads tables, keys and foreign keys straight from each SQLite file
  migrate         - brings an existing Phase 1/2 database up to the Phase 3 schema, in place
  medicine_views  - multi-table joins that show one medicine spread across a source's tables
  nosql_store     - DB1's JSON document collections and their declared document references
  inspect         - CLI report used to validate all of the above

Every function takes the database it works on as an argument or resolves it through
integration.uncertainty.paths, so each source can be inspected on its own machine.
Nothing here merges the four databases.
"""
