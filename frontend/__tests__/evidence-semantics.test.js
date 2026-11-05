import { describe, expect, it } from 'vitest';
import '../evidence-semantics.js';

describe('canonical four-state evidence wording', () => {
  it('uses the exact Section 19 wording for every state', () => {
    const { interpretations } = globalThis.KairosEvidenceSemantics;
    expect(interpretations.OBSERVED).toBe('At least one source value was observed to contribute to at least one target output in this run. This does not imply contribution to every row or every run.');
    expect(interpretations.REFUTED_FOR_RUN).toBe('No propagation was established for this run under the declared complete-evaluation conditions. This is not a universal claim that the dependency can never occur.');
    expect(interpretations.POSSIBLE).toBe('Static analysis permits this dependency, but available evidence is insufficient to establish whether propagation occurred in this run.');
    expect(interpretations.UNKNOWN).toBe('Kairos cannot safely evaluate this dependency because relevant semantics, identity, schema or instrumentation is unsupported or ambiguous.');
  });

  it('does not turn missing runtime events into a negative state', () => {
    const semantics = globalThis.KairosEvidenceSemantics;
    expect(semantics.isNegative('UNKNOWN')).toBe(false);
    expect(semantics.isNegative('POSSIBLE')).toBe(false);
    expect(semantics.interpret('UNKNOWN')).toContain('cannot safely evaluate');
    expect(semantics.interpret('no runtime event')).toBe(semantics.interpretations.UNKNOWN);
    expect(semantics.isNegative('REFUTED_FOR_RUN')).toBe(true);
  });
});
