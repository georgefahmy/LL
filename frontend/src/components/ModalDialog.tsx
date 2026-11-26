import { useEffect, useId, useRef, type ReactNode } from "react";
import { X } from "lucide-react";

interface ModalDialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  wide?: boolean;
  lightDismiss?: boolean;
  children: ReactNode;
}

export function ModalDialog({
  open,
  onClose,
  title,
  wide = false,
  lightDismiss = true,
  children,
}: ModalDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const pressedOutsideRef = useRef(false);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    const handleClose = () => {
      dialog.returnValue = "";
      onClose();
    };

    const isOutside = (e: PointerEvent) => {
      const r = dialog.getBoundingClientRect();
      return (
        e.clientX < r.left ||
        e.clientX > r.right ||
        e.clientY < r.top ||
        e.clientY > r.bottom
      );
    };

    const handlePointerDown = (e: PointerEvent) => {
      if (!lightDismiss) return;
      pressedOutsideRef.current = isOutside(e);
    };

    const handlePointerUp = (e: PointerEvent) => {
      if (!lightDismiss) return;
      if (pressedOutsideRef.current && isOutside(e) && dialog.open) {
        dialog.close("backdrop");
      }
      pressedOutsideRef.current = false;
    };

    dialog.addEventListener("close", handleClose);
    if (!("closedBy" in HTMLDialogElement.prototype)) {
      dialog.addEventListener("pointerdown", handlePointerDown);
      dialog.addEventListener("pointerup", handlePointerUp);
    }

    return () => {
      dialog.removeEventListener("close", handleClose);
      dialog.removeEventListener("pointerdown", handlePointerDown);
      dialog.removeEventListener("pointerup", handlePointerUp);
    };
  }, [onClose, lightDismiss]);

  const dialogAttrs: Record<string, string> = lightDismiss
    ? { closedby: "any" }
    : {};

  return (
    <dialog
      ref={dialogRef}
      aria-labelledby={titleId}
      className={wide ? "ll-dialog-wide w-full" : "w-full"}
      {...dialogAttrs}
    >
      <div className="flex flex-col max-h-[90vh]">
        <div
          className="flex items-center justify-between gap-4 px-5 py-3.5 border-b"
          style={{ borderColor: "var(--border-subtle)" }}
        >
          <h2 id={titleId} className="text-lg font-semibold m-0">
            {title}
          </h2>
          <button
            type="button"
            onClick={() => dialogRef.current?.close("button")}
            aria-label={`Close ${title}`}
            className="min-w-8 min-h-8 inline-flex items-center justify-center rounded-lg hover:opacity-80 cursor-pointer"
            style={{ backgroundColor: "var(--bg-muted)" }}
          >
            <X className="w-4 h-4" aria-hidden="true" />
          </button>
        </div>
        <div className="p-5 overflow-y-auto">{children}</div>
      </div>
    </dialog>
  );
}
