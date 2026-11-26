import { BookOpen } from "lucide-react";

import { ModalDialog } from "./ModalDialog";

interface LookupPopoverProps {
  result: { term: string; source: string; summary: string } | null;
  loading: boolean;
  onClose: () => void;
}

export function LookupPopover({ result, loading, onClose }: LookupPopoverProps) {
  return (
    <ModalDialog
      open={loading || Boolean(result)}
      onClose={onClose}
      title={result ? `Lookup: ${result.term}` : "Looking up selection..."}
    >
      {loading ? (
        <p className="text-sm" style={{ color: "var(--text-secondary)" }}>
          Fetching definition / Wikipedia summary...
        </p>
      ) : (
        result && (
          <div className="space-y-3">
            <div className="inline-flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-full ll-muted">
              <BookOpen className="w-3.5 h-3.5" aria-hidden="true" />
              Source: {result.source}
            </div>
            <p className="text-sm whitespace-pre-line leading-relaxed">
              {result.summary}
            </p>
          </div>
        )
      )}
    </ModalDialog>
  );
}
