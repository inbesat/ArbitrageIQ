/**
 * An actionable failure: what went wrong and a way to retry.
 *
 * `plans/PRD.md` §4.5 forbids a raw stack trace; `detail` is always the backend's own
 * plain-English message or a fixed sentence written here. Never the bare status code.
 *
 * The title and the mark say "failure" in words and in shape, so the panel does not rely
 * on its red tint alone.
 */
export function ErrorState({
  title,
  detail,
  onRetry,
}: {
  title: string;
  detail?: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="rounded-card border border-loss/30 bg-loss-wash p-5 shadow-card sm:p-6">
      <div className="flex items-start gap-3.5">
        <span
          aria-hidden="true"
          className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-loss text-white"
        >
          <svg
            viewBox="0 0 24 24"
            className="h-[18px] w-[18px]"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
          >
            <path d="M12 7.5v5.25" />
            <path d="M12 16.5h.01" />
          </svg>
        </span>

        <div className="min-w-0 flex-1">
          <h2 className="text-title text-loss">{title}</h2>
          <p className="mt-1.5 text-body text-navy">{detail ?? 'Something went wrong.'}</p>
          {onRetry ? (
            <button
              type="button"
              onClick={onRetry}
              className="mt-4 inline-flex min-h-[44px] items-center rounded border border-loss bg-surface px-4 text-body font-semibold text-loss transition-colors duration-fast ease-standard hover:bg-loss hover:text-white"
            >
              Try again
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
