export function getActionGuidance(anomalyType, source, amountDifference) {
  const type = (anomalyType ?? '').toLowerCase();
  const isBank = (source ?? '').toLowerCase().includes('bank');

  if (type.includes('missing settlement')) {
    return 'Payment captured without corresponding gateway settlement batch. Check processor payout queue.';
  }
  if (type.includes('missing bank')) {
    return 'Gateway marked settled, but credit is absent from bank statement. Verify wire clearing reference.';
  }
  if (type.includes('amount mismatch') || type.includes('mismatch')) {
    if (!isBank) {
      return 'Actual net settlement differs from expected payout formula. Inspect gateway fee/refund deductions.';
    }

    const variance = Number(amountDifference);
    if (Number.isFinite(variance)) {
      if (variance > 0) {
        return 'Bank credit is lower than the settled net payout (short-credit). Check bank wire fees or adjustments.';
      }
      if (variance < 0) {
        return 'Bank credit exceeds the settled net payout. Review for an excess, possible duplicate, or incorrect credit.';
      }
      return 'Bank credit equals the settled net payout; no amount mismatch is present.';
    }
    return 'Bank credit differs from the settled net payout. Compare the bank statement with processor records.';
  }
  return 'Inspect the linked source ledger. AI investigation is not connected yet.';
}
