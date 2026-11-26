import { useId, useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";

export interface TableColumn<T> {
  key: string;
  label: string;
  type?: "text" | "number";
  sortable?: boolean;
  title?: string;
  render?: (row: T) => ReactNode;
}

interface DataTableProps<T extends Record<string, unknown>> {
  caption: string;
  columns: TableColumn<T>[];
  rows: T[];
  rowKey: (row: T, idx: number) => string;
  highlightRow?: (row: T) => boolean;
}

const collator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: "base",
});

export function DataTable<T extends Record<string, unknown>>({
  caption,
  columns,
  rows,
  rowKey,
  highlightRow,
}: DataTableProps<T>) {
  const captionId = useId();
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<"ascending" | "descending">("descending");
  const [announcement, setAnnouncement] = useState("");

  const sortedRows = useMemo(() => {
    if (!sortCol) return rows;
    const colDef = columns.find((c) => c.key === sortCol);
    const factor = sortDir === "ascending" ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = a[sortCol];
      const bv = b[sortCol];
      if (colDef?.type === "number") {
        const an = Number(av ?? -Infinity);
        const bn = Number(bv ?? -Infinity);
        if (!Number.isNaN(an) && !Number.isNaN(bn)) {
          return factor * (an - bn);
        }
      }
      return factor * collator.compare(String(av ?? ""), String(bv ?? ""));
    });
  }, [rows, columns, sortCol, sortDir]);

  const handleSort = (col: TableColumn<T>) => {
    const nextDir =
      sortCol === col.key && sortDir === "ascending" ? "descending" : "ascending";
    setSortCol(col.key);
    setSortDir(nextDir);
    setAnnouncement(`Sorted by ${col.label}, ${nextDir}, ${rows.length} rows`);
  };

  return (
    <div className="space-y-1">
      <div role="status" className="visually-hidden">
        {announcement}
      </div>
      <div
        tabIndex={0}
        role="region"
        aria-labelledby={captionId}
        className="overflow-x-auto max-h-[68vh] rounded-xl border"
        style={{ borderColor: "var(--border-subtle)" }}
      >
        <table className="w-full border-collapse text-xs sm:text-[13px] text-left">
          <caption id={captionId} className="visually-hidden">
            {caption}
          </caption>
          <thead
            className="sticky top-0 z-10"
            style={{ backgroundColor: "var(--bg-muted)" }}
          >
            <tr>
              {columns.map((col) => {
                const isSortable = col.sortable !== false;
                const activeSort = sortCol === col.key ? sortDir : undefined;
                return (
                  <th
                    key={col.key}
                    scope="col"
                    aria-sort={activeSort}
                    title={col.title}
                    className={`border-b font-semibold whitespace-nowrap ${
                      isSortable ? "p-0" : "px-2 py-2"
                    }`}
                    style={{ borderColor: "var(--border-subtle)" }}
                  >
                    {isSortable ? (
                      <button
                        type="button"
                        onClick={() => handleSort(col)}
                        className="w-full min-h-9 px-2 py-2 inline-flex items-center gap-1 text-left hover:opacity-80 cursor-pointer"
                      >
                        <span>{col.label}</span>
                        {activeSort === "ascending" ? (
                          <ArrowUp className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                        ) : activeSort === "descending" ? (
                          <ArrowDown className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
                        ) : (
                          <ArrowUpDown
                            className="w-3.5 h-3.5 opacity-40 shrink-0"
                            aria-hidden="true"
                          />
                        )}
                      </button>
                    ) : (
                      col.label
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {sortedRows.map((row, idx) => {
              const highlighted = highlightRow ? highlightRow(row) : false;
              return (
                <tr
                  key={rowKey(row, idx)}
                  className={`border-b transition-colors ${
                    highlighted
                      ? "bg-amber-500/20"
                      : idx % 2 === 1
                        ? "bg-slate-500/5"
                        : ""
                  }`}
                  style={{ borderColor: "var(--border-subtle)" }}
                >
                  {columns.map((col) => (
                    <td key={col.key} className="px-2 py-1.5 whitespace-nowrap">
                      {col.render ? col.render(row) : String(row[col.key] ?? "")}
                    </td>
                  ))}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
