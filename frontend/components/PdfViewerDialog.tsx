"use client";

import { Download } from "lucide-react";

import { Dialog } from "@/components/ui/dialog";

interface Props {
  open: boolean;
  onClose: () => void;
  title: string;
  src: string;
  downloadUrl?: string;
}

export function PdfViewerDialog({ open, onClose, title, src, downloadUrl }: Props) {
  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={title}
      size="lg"
      footer={
        downloadUrl ? (
          <a
            href={downloadUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex h-9 items-center gap-1.5 rounded-md border border-primary px-3 text-sm font-medium text-primary transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Download className="h-4 w-4" aria-hidden="true" />
            Baixar arquivo
          </a>
        ) : null
      }
    >
      {open && (
        <iframe
          src={src}
          title={title}
          className="h-[70vh] w-full rounded-md border border-border bg-muted"
        />
      )}
    </Dialog>
  );
}
