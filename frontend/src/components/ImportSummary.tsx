/**
 * The result of one import run or dry run (task T14).
 *
 * Counts only. Nothing here is a money value, and nothing is parsed — the numbers
 * come back from the backend as integers.
 */
import type { ImportReport } from '../api/types';

interface ImportSummaryProps {
  report: ImportReport;
  /** True when the run only validated and deliberately persisted nothing. */
  dryRun: boolean;
}

function Stat({ label, value, tone = 'navy' }: { label: string; value: number; tone?: 'navy' | 'loss' }) {
  return (
    <div className="card px-4 py-3">
      <dt className="eyebrow">{label}</dt>
      <dd
        className={`tnum mt-1.5 text-figure-sm font-semibold ${
          tone === 'loss' ? 'text-loss' : 'text-navy'
        }`}
      >
        {value}
      </dd>
    </div>
  );
}

export function ImportSummary({ report, dryRun }: ImportSummaryProps) {
  return (
    <div role="status" className="space-y-3.5">
      <p className="text-body font-medium text-navy">
        {dryRun
          ? 'Dry run finished. Nothing was saved.'
          : 'Import finished. A repeat of the same file changes nothing.'}
      </p>

      <dl className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <Stat label={dryRun ? 'Valid rows' : 'Imported'} value={report.imported} />
        {!dryRun && <Stat label="Already present" value={report.skipped ?? 0} />}
        <Stat
          label="Rejected"
          value={report.rejected_total}
          tone={report.rejected_total > 0 ? 'loss' : 'navy'}
        />
      </dl>

      {(report.warnings?.length ?? 0) > 0 && (
        <ul className="space-y-1 text-caption text-warn">
          {report.warnings?.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
