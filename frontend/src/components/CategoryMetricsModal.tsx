import type { CategoryMetric } from "../types";
import { ModalDialog } from "./ModalDialog";

interface CategoryMetricsModalProps {
  open: boolean;
  onClose: () => void;
  username: string;
  metrics: Record<string, CategoryMetric>;
}

export function CategoryMetricsModal({
  open,
  onClose,
  username,
  metrics,
}: CategoryMetricsModalProps) {
  const sorted = Object.entries(metrics).sort(
    (a, b) => b[1].percent - a[1].percent
  );

  return (
    <ModalDialog
      open={open}
      onClose={onClose}
      title={`Category Metrics - ${username}`}
    >
      {sorted.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          No category metrics available for this season.
        </p>
      ) : (
        <div className="space-y-2.5">
          {sorted.map(([cat, m]) => {
            const pct = (m.percent * 100).toFixed(1);
            return (
              <div key={cat} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="font-medium">
                    {cat}{" "}
                    <span style={{ color: "var(--text-secondary)" }}>
                      ({m.correct}/{m.total})
                    </span>
                  </span>
                  <span className="font-mono font-semibold">{pct}%</span>
                </div>
                <div
                  className="w-full h-2.5 rounded-full overflow-hidden"
                  style={{ backgroundColor: "var(--bg-muted)" }}
                >
                  <div
                    className="h-full bg-blue-600 rounded-full"
                    style={{ width: `${Math.min(100, m.percent * 100)}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </ModalDialog>
  );
}
