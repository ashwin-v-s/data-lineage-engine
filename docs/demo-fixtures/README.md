# Repeatable import examples

These synthetic files are safe to use for the local-file, SQL parsing, and dbt manifest demos. They contain no customer data. The SQL adapter parses the file and does not execute SQL. The dbt manifest records declared dependencies; it does not prove a dbt run occurred.

- `demo_orders.csv`: header-only metadata extraction; sample rows are ignored by the CSV headers adapter.
- `demo_revenue.sql`: declared target and source candidates for SQL parsing.
- `manifest.json`: one dbt model, two sources, and declared dependencies.
- `metadata_graph.json`: Kairos `kairos.ingest.v1` graph for explicit asset and edge import.

In the app, open **Import metadata**, select a file, choose the matching adapter (`CSV headers`, `SQL file`, `dbt manifest`, or `Kairos metadata graph`), validate the preview, then explicitly commit. A successful local parse is not proof that an authenticated catalog import succeeded; verify it in the catalog after commit.
