import { ExternalLink, Image as ImageIcon } from "lucide-react";

import type { QuestionItem } from "../types";
import { ModalDialog } from "./ModalDialog";

export interface InspectedQuestion {
  qcode: string;
  questionData?: QuestionItem;
  fallbackText?: string;
  correct?: boolean;
  llUrl?: string;
}

interface QuestionDrawerProps {
  items: InspectedQuestion[];
  onClose: () => void;
  onOpenImage: (url: string) => void;
}

export function QuestionDrawer({
  items,
  onClose,
  onOpenImage,
}: QuestionDrawerProps) {
  return (
    <ModalDialog
      open={items.length > 0}
      onClose={onClose}
      title={
        items.length === 1
          ? `Question ${items[0].qcode}`
          : `Inspected Questions (${items.length})`
      }
      wide
    >
      <div className="space-y-4">
        {items.map((item) => {
          const qd = item.questionData;
          const text = qd?.question || item.fallbackText || "Question text unavailable.";
          const llUrl = qd?.url || item.llUrl;
          return (
            <div key={item.qcode} className="ll-muted p-4 rounded-xl space-y-2.5">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono font-bold text-sm">{item.qcode}</span>
                  {qd?.category && (
                    <span className="text-xs px-2 py-0.5 rounded-full ll-card font-medium">
                      {qd.category}
                    </span>
                  )}
                  {item.correct !== undefined && (
                    <span
                      className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
                        item.correct
                          ? "bg-emerald-600/20 text-emerald-700 dark:text-emerald-300"
                          : "bg-rose-600/20 text-rose-700 dark:text-rose-300"
                      }`}
                    >
                      {item.correct ? "Correct" : "Incorrect"}
                    </span>
                  )}
                </div>
                {llUrl && (
                  <a
                    href={llUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 underline"
                  >
                    Open on LL
                    <ExternalLink className="w-3 h-3" aria-hidden="true" />
                  </a>
                )}
              </div>

              <p className="text-sm leading-relaxed">{text}</p>

              {qd && (
                <div className="flex flex-wrap items-center justify-between gap-2 pt-1 text-sm">
                  <div>
                    <span style={{ color: "var(--text-secondary)" }}>Answer: </span>
                    <span className="font-semibold text-emerald-700 dark:text-emerald-300">
                      {qd.answer}
                    </span>
                  </div>
                  <div className="flex items-center gap-3">
                    {qd.clickable_link && (
                      <button
                        type="button"
                        onClick={() => onOpenImage(qd.clickable_link)}
                        className="inline-flex items-center gap-1 text-xs text-blue-600 dark:text-blue-400 underline cursor-pointer"
                      >
                        <ImageIcon className="w-3.5 h-3.5" aria-hidden="true" />
                        View Media
                      </button>
                    )}
                    <span className="text-xs font-mono px-2 py-0.5 rounded ll-card">
                      {qd.percent}% Correct
                    </span>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </ModalDialog>
  );
}
