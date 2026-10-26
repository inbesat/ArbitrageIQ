/**
 * Renders one monetary value exactly as the backend sent it.
 *
 * The value is a decimal string (ADR-024). It is never parsed, rounded or reformatted —
 * converting money to a JavaScript number is banned in this codebase
 * (`plans/TECH_STACK.md` §3.1, `AGENTS.md` rule 7). All this does is add the currency
 * symbol and, for a negative figure, an explicit minus sign and the word "loss", so the
 * meaning survives for a reader who cannot distinguish red from navy
 * (`plans/ACCEPTANCE_TESTS.md` AT-10.4, AT-10.12).
 */
export function MoneyCell({
  value,
  currency = '₹',
  className = '',
}: {
  value: string;
  currency?: string;
  className?: string;
}) {
  if (value === 'n/a') {
    return (
      <span className={`tnum text-muted ${className}`} title="Not defined for this row">
        n/a
      </span>
    );
  }

  const isLoss = value.startsWith('-');
  const magnitude = isLoss ? value.slice(1) : value;

  // The marker leads the figure rather than trailing it: in a right-aligned column the
  // rightmost character is what lines up, so a trailing word would push every loss out of
  // alignment with the positive figures above and below it.
  return (
    <span
      className={`tnum inline-flex items-baseline gap-1.5 whitespace-nowrap ${
        isLoss ? 'text-loss' : 'text-navy'
      } ${className}`}
    >
      {isLoss ? (
        <span className="text-micro font-semibold uppercase tracking-wide">loss</span>
      ) : null}
      <span>
        {isLoss ? '−' : ''}
        {currency}
        {magnitude}
      </span>
    </span>
  );
}
