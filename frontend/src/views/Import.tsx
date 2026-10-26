/**
 * Import: load a catalogue and the transactions it explains (task T14).
 *
 * The catalogue must land first. The API rejects a transaction whose sku is absent
 * from `products` (AT-5.14), so the kind selector defaults to `products` and the
 * copy says plainly that the order matters.
 *
 * Nothing here reads, parses or computes a money value. The CSV goes up as
 * multipart bytes; every count and every rejection reason comes back already
 * formatted by the backend (`AGENTS.md` rule 7).
 */
import { useRef, useState } from 'react';

import { apiFetch } from '../api/client';
import type { ImportReport } from '../api/types';
import { ErrorState } from '../components/ErrorState';
import { ImportSummary } from '../components/ImportSummary';
import { RejectionTable } from '../components/RejectionTable';
import { Reveal } from '../components/Reveal';

type Kind = 'products' | 'transactions';

const CAPS = 'Files are read as text and capped at 5 MB and 20,000 data rows.';

const KIND_LABEL: Record<Kind, string> = {
  products: 'Products (the catalogue)',
  transactions: 'Transactions (what sold)',
};

const BUTTON =
  'lift inline-flex min-h-[44px] items-center rounded px-4 text-sm font-semibold shadow-card ' +
  'transition-colors duration-fast ease-standard disabled:cursor-not-allowed disabled:opacity-55';
const PRIMARY = `${BUTTON} bg-teal text-white hover:bg-teal-dark hover:shadow-glow`;
const SECONDARY = `${BUTTON} border border-rule bg-surface text-navy hover:border-teal hover:text-teal`;

export function Import() {
  const [kind, setKind] = useState<Kind>('products');
  const [busy, setBusy] = useState(false);
  const [outcome, setOutcome] = useState<{ report: ImportReport; dryRun: boolean } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  function settle(state: Awaited<ReturnType<typeof apiFetch<ImportReport>>>, dryRun: boolean) {
    setBusy(false);
    if (state.status === 'ready') {
      setOutcome({ report: state.data, dryRun });
      return;
    }
    // `apiFetch` never throws and never surfaces a stack trace: a network drop, a
    // 413, a 422 or a 500 all arrive as one plain sentence (AT-10.15).
    setOutcome(null);
    setProblem(
      state.status === 'error' ? state.detail : 'The request returned no result. Try again.',
    );
  }

  async function sendFile(dryRun: boolean) {
    const file = fileInput.current?.files?.[0];
    if (!file) {
      setProblem('Choose a CSV file first, then run the import.');
      return;
    }
    setBusy(true);
    setProblem(null);
    setOutcome(null);

    const form = new FormData();
    form.append('kind', kind);
    form.append('file', file);
    // Deliberately no Content-Type header: the browser must set the multipart
    // boundary itself or the upload fails.
    settle(
      await apiFetch<ImportReport>(dryRun ? '/import/validate' : '/import', {
        method: 'POST',
        body: form,
      }),
      dryRun,
    );
  }

  async function loadSample(sample: Kind) {
    setBusy(true);
    setProblem(null);
    setOutcome(null);
    settle(
      await apiFetch<ImportReport>('/import/sample', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: sample }),
      }),
      false,
    );
  }

  return (
    <section className="enter space-y-7">
      <Reveal className="space-y-2.5 border-b border-rule pb-6">
        <p className="eyebrow">Step 2 · Your data</p>
        <h1 className="text-display text-navy sm:text-display-lg">Import</h1>
        <p className="max-w-[68ch] text-body text-muted">
          Load the catalogue and the transactions the figures are computed from.
        </p>
      </Reveal>

      <Reveal className="space-y-4">
        <div className="card p-5 sm:p-6">
          <h2 className="eyebrow">1 · What are you loading?</h2>
          <div
            role="radiogroup"
            aria-label="Which file are you loading?"
            className="mt-3 grid gap-2 sm:grid-cols-2"
          >
            {(Object.keys(KIND_LABEL) as Kind[]).map((value) => (
              <button
                key={value}
                type="button"
                role="radio"
                aria-checked={kind === value}
                onClick={() => setKind(value)}
                className={`flex min-h-[44px] items-center justify-between gap-3 rounded border px-4 py-3 text-left text-body font-medium transition-colors duration-fast ease-standard ${
                  kind === value
                    ? 'border-teal bg-teal text-white'
                    : 'border-rule bg-canvas text-navy hover:border-teal/60'
                }`}
              >
                {KIND_LABEL[value]}
                {/* A tick as well as the fill, so the choice is not carried by colour. */}
                <svg
                  aria-hidden="true"
                  viewBox="0 0 16 16"
                  className={`h-4 w-4 shrink-0 transition-opacity duration-fast ease-standard ${
                    kind === value ? 'opacity-100' : 'opacity-0'
                  }`}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="m3.5 8.5 3 3 6-6.5" />
                </svg>
              </button>
            ))}
          </div>
          <p className="mt-3 text-caption text-muted">
            The catalogue has to be loaded before the transactions: a transaction that names a SKU
            the catalogue does not contain is rejected, and a rejected row is never imported.
          </p>
        </div>

        <div className="card p-5 sm:p-6">
          <h2 className="eyebrow">2 · Choose the file</h2>
          <div className="mt-3 flex flex-col gap-3">
            <label htmlFor="csv" className="text-body font-medium text-navy">
              CSV file
            </label>
            <input
              ref={fileInput}
              id="csv"
              type="file"
              accept=".csv,text/csv"
              aria-describedby="csv-caps"
              className="w-full rounded border border-rule bg-canvas px-3 py-2.5 text-body text-navy file:mr-3 file:rounded file:border-0 file:bg-navy file:px-3 file:py-2 file:text-caption file:font-semibold file:text-white"
            />
            <p id="csv-caps" className="text-caption text-muted">
              {CAPS}
            </p>
          </div>

          <div className="mt-5 flex flex-wrap gap-3">
            <button type="button" className={PRIMARY} disabled={busy} onClick={() => sendFile(false)}>
              {busy ? 'Working…' : 'Import'}
            </button>
            <button
              type="button"
              className={SECONDARY}
              disabled={busy}
              onClick={() => sendFile(true)}
            >
              Dry run only
            </button>
          </div>
          <p className="mt-2.5 text-caption text-muted">
            A dry run validates the file and saves nothing; use it to see the rejections first.
          </p>
        </div>

        <div className="card p-5 sm:p-6">
          <h2 className="eyebrow">Or explore with the sample</h2>
          <p className="mt-2 text-body text-muted">
            The bundled synthetic sample is illustrative only — it is not real demand and not a
            forecast. Loading it twice changes nothing.
          </p>
          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              className={SECONDARY}
              disabled={busy}
              onClick={() => loadSample('products')}
            >
              Load sample catalogue
            </button>
            <button
              type="button"
              className={SECONDARY}
              disabled={busy}
              onClick={() => loadSample('transactions')}
            >
              Load sample transactions
            </button>
          </div>
        </div>
      </Reveal>

      {/* Both of these are answers to the button the reader just pressed, so they fade in on
          mount rather than waiting to be scrolled into view (`Reveal` is viewport-gated and
          would leave them at `opacity: 0` below the fold). */}
      {problem !== null && (
        <div className="enter">
          <ErrorState title="That import did not go through" detail={problem} />
        </div>
      )}

      {outcome !== null && (
        <div className="enter space-y-4">
          <ImportSummary report={outcome.report} dryRun={outcome.dryRun} />
          <RejectionTable rejections={outcome.report.rejected} />
          {!outcome.dryRun && (
            <div>
              <button
                type="button"
                className={PRIMARY}
                onClick={() => {
                  // A full load, not a client-side route change: the app-wide
                  // readouts (demo-data badge, assumptions) are mounted once in the
                  // shell, so only a fresh load reflects the data that just landed.
                  window.location.assign('/');
                }}
              >
                Show the portfolio
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
