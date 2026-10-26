import type { ReactNode } from 'react';

/**
 * What every view shows before it has data.
 *
 * `plans/ACCEPTANCE_TESTS.md` AT-10.1 requires an informative empty state, never a blank
 * panel and never a crash. Each view supplies its own title, message and next step, so
 * the copy is always specific to that view rather than a generic "No items".
 *
 * The mark above the title is decorative and `aria-hidden`: it signals "nothing here"
 * at a glance without adding a word to read.
 */
export function EmptyState({
  title,
  message,
  action,
}: {
  title: string;
  message: string;
  action?: ReactNode;
}) {
  return (
    <div role="status" className="card px-6 py-14 sm:px-10 sm:py-16">
      <div className="mx-auto flex max-w-[58ch] flex-col items-center text-center">
        <span
          aria-hidden="true"
          className="grid h-12 w-12 place-items-center rounded-full border border-teal/20 bg-teal-wash text-teal"
        >
          <svg
            viewBox="0 0 24 24"
            className="h-[22px] w-[22px]"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M3.75 8.25 12 3.5l8.25 4.75v7.5L12 20.5l-8.25-4.75v-7.5Z" />
            <path d="M3.75 8.25 12 13l8.25-4.75" />
            <path d="M12 13v7.5" />
          </svg>
        </span>
        <h2 className="mt-5 text-title text-navy">{title}</h2>
        <p className="mt-2.5 text-body text-muted">{message}</p>
        {action ? <div className="mt-7">{action}</div> : null}
      </div>
    </div>
  );
}
