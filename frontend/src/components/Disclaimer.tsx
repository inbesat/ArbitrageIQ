/**
 * The `plans/BUSINESS_RULES.md` §7 disclaimer — one string, one component.
 *
 * §7 requires this text "to appear on the Methodology view and beside any GST control".
 * Both places render this component, so the sentence exists once in the source and can
 * never drift between the two screens (task T16).
 *
 * Do not reword, split or shorten `DISCLAIMER_TEXT`. `plans/BUSINESS_RULES.md` is
 * authoritative for it, and `plans/ACCEPTANCE_TESTS.md` AT-10.11 checks it verbatim.
 */

/** §7, verbatim. */
export const DISCLAIMER_TEXT =
  'Marketplace fee rates, GST rates and thresholds in this tool are illustrative demo ' +
  'assumptions with a recorded effective date. They are not current Amazon or Indian tax ' +
  'figures. This tool is not tax advice, is not an accounting system, and does not ' +
  'determine your GST registration obligations or ITC eligibility. Verify with a ' +
  'qualified professional.';

/** The same warn-tinted surface the disclosure and error panels use. */
export function Disclaimer() {
  return (
    <blockquote className="rounded-card border border-warn/40 bg-warn-wash px-4 py-3.5 text-body text-navy">
      {DISCLAIMER_TEXT}
    </blockquote>
  );
}
