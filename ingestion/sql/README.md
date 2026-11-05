# ingestion/sql (M1)

**Status: implemented for a bounded SQL subset.** `SQLGlotLineageProvider`
implements `contracts.interfaces.StaticLineageProvider` and emits static
dependency candidates. It never proves that a query ran. Unsupported
constructs, parse failures, or missing schema are reported as `UNSUPPORTED`.

See `SUPPORT_MATRIX.md` for the supported subset and
`../../tests/test_static_corpus.py` plus `../../tests/test_static_unsupported.py`
for the current regression corpus. New dialect/construct support needs a
fixture with expected dependencies and an explicit support-matrix update.
