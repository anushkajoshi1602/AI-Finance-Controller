import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import { getActionGuidance } from '../src/utils/anomalyGuidance.js';

describe('bank reconciliation anomaly guidance', () => {
  it('describes a short-credit when expected minus actual is positive', () => {
    const text = getActionGuidance('Amount Mismatch', 'Bank Reconciliation', '12.50');
    assert.match(text, /lower than the settled net payout.*short-credit/i);
  });

  it('describes an excess credit without asserting a cause when expected minus actual is negative', () => {
    const text = getActionGuidance('Amount Mismatch', 'Bank Reconciliation', '-12.50');
    assert.match(text, /exceeds the settled net payout/i);
    assert.match(text, /possible duplicate, or incorrect credit/i);
  });

  it('does not describe equal bank and expected amounts as a mismatch', () => {
    const text = getActionGuidance('Amount Mismatch', 'Bank Reconciliation', '0.00');
    assert.match(text, /equals the settled net payout; no amount mismatch/i);
  });
});
