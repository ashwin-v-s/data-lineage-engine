/* Canonical, verbatim Section 19 text shared by all four reasoning states. */
(function installEvidenceSemantics(root) {
  'use strict';
  const interpretations = Object.freeze({
    OBSERVED: 'At least one source value was observed to contribute to at least one target output in this run. This does not imply contribution to every row or every run.',
    REFUTED_FOR_RUN: 'No propagation was established for this run under the declared complete-evaluation conditions. This is not a universal claim that the dependency can never occur.',
    POSSIBLE: 'Static analysis permits this dependency, but available evidence is insufficient to establish whether propagation occurred in this run.',
    UNKNOWN: 'Kairos cannot safely evaluate this dependency because relevant semantics, identity, schema or instrumentation is unsupported or ambiguous.',
  });
  root.KairosEvidenceSemantics = Object.freeze({
    interpretations,
    interpret(state) {
      const normalized = String(state || '').toUpperCase();
      return interpretations[normalized] || interpretations.UNKNOWN;
    },
    isNegative(state) {
      return String(state || '').toUpperCase() === 'REFUTED_FOR_RUN';
    },
  });
})(globalThis);
