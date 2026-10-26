/**
 * The per-row rejection report (task T14; `plans/ACCEPTANCE_TESTS.md` AT-10.3).
 *
 * A rejected row is never silently dropped: it is listed with its row number, the
 * field at fault, the value exactly as the backend read it, and the reason. The
 * value is rendered verbatim — it is never coerced, parsed or re-formatted.
 *
 * The table scrolls inside its own box rather than pushing the page wide, so a
 * phone-width viewport still has no horizontal scroll (AT-10.12). The reason is the
 * payload of this table, so it is set in ink while the value it rejected stays muted,
 * and it wraps rather than truncating.
 */
import type { Rejection } from '../api/types';

export function RejectionTable({ rejections }: { rejections: Rejection[] }) {
  if (rejections.length === 0) {
    return null;
  }

  return (
    <div className="table-scroll card" data-lenis-prevent>
      <table className="w-full min-w-[36rem] border-collapse text-left text-body">
        <caption className="px-4 pt-4 pb-3 text-left text-caption text-muted">
          Rejected rows — {rejections.length} listed, each with the field it failed on.
        </caption>
        <thead className="table-head">
          <tr>
            <th scope="col" className="eyebrow px-4 py-2.5">
              Row
            </th>
            <th scope="col" className="eyebrow px-4 py-2.5">
              Field
            </th>
            <th scope="col" className="eyebrow px-4 py-2.5">
              Value
            </th>
            <th scope="col" className="eyebrow px-4 py-2.5">
              Reason
            </th>
          </tr>
        </thead>
        <tbody>
          {rejections.map((item, index) => (
            <tr
              key={`${item.row}-${item.field}-${index}`}
              className="border-b border-rule/70 transition-colors duration-fast ease-standard last:border-b-0 hover:bg-canvas"
            >
              <td className="h-12 px-4">
                <span className="tnum inline-flex min-w-[2.25rem] items-center justify-center rounded-full bg-canvas px-2 py-0.5 text-caption font-medium text-navy">
                  {item.row}
                </span>
              </td>
              <td className="h-12 px-4 font-semibold text-navy">{item.field}</td>
              <td className="tnum h-12 px-4 text-muted">{item.value ?? '—'}</td>
              <td className="h-12 min-w-[18rem] px-4 text-navy">{item.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
