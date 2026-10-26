/**
 * The persistent demo-data marker.
 *
 * `plans/ACCEPTANCE_TESTS.md` AT-10.2 requires it to be visible whenever the synthetic
 * sample is loaded, and `plans/PRD.md` §5 requires it to be unmistakable. It states the
 * fact in words, so it does not depend on colour, and it names the assumptions rather
 * than only the data.
 */
export function DemoBadge() {
  return (
    <p
      role="status"
      className="inline-flex flex-wrap items-center gap-x-2 gap-y-0.5 rounded border border-warn/40 bg-warn-wash px-3 py-1.5 text-caption text-warn"
    >
      <span className="font-semibold uppercase tracking-wide">Demo data</span>
      <span className="text-navy">synthetic sample · illustrative assumptions</span>
    </p>
  );
}
