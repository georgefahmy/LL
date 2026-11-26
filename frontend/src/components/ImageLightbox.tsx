import { useState } from "react";

import { ModalDialog } from "./ModalDialog";

interface ImageLightboxProps {
  imageUrl: string | null;
  onClose: () => void;
}

export function ImageLightbox({ imageUrl, onClose }: ImageLightboxProps) {
  const [failed, setFailed] = useState(false);
  const proxied = imageUrl
    ? `/api/proxy/image?url=${encodeURIComponent(imageUrl)}`
    : null;

  return (
    <ModalDialog
      open={Boolean(proxied)}
      onClose={() => {
        setFailed(false);
        onClose();
      }}
      title="Question Media"
      wide
    >
      {proxied && (
        <div className="flex flex-col items-center gap-3">
          {failed ? (
            <p className="text-sm text-red-600 dark:text-red-400">
              Could not load image from LearnedLeague.
            </p>
          ) : (
            <img
              src={proxied}
              alt="Question visual clue"
              onError={() => setFailed(true)}
              className="max-w-full max-h-[70vh] rounded-lg object-contain"
            />
          )}
          <a
            href={imageUrl ?? "#"}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-blue-600 dark:text-blue-400 underline"
          >
            Open original on learnedleague.com
          </a>
        </div>
      )}
    </ModalDialog>
  );
}
