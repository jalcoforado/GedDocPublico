"use client";

import { Bus } from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/ui/page-header";
import { CARDS } from "@/lib/transporte-hub";

export default function TransporteReguladoHubPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        icon={Bus}
        title="Transporte Regulado"
        description="Gestão de permissionários e do transporte público regulado do município."
      />
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {CARDS.map((c) => {
          const Icon = c.icon;
          const content = (
            <>
              <div className="mb-3 inline-flex h-10 w-10 items-center justify-center rounded-md bg-brand/12 text-brand">
                <Icon className="h-5 w-5" aria-hidden="true" />
              </div>
              <div className="flex items-center gap-2">
                <h2 className="font-semibold text-foreground">{c.title}</h2>
                {!c.ready && (
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                    em estruturação
                  </span>
                )}
              </div>
              <p className="mt-1 text-sm text-foreground-muted">{c.desc}</p>
            </>
          );
          return c.ready && c.href ? (
            <Link
              key={c.title}
              href={c.href}
              className="group rounded-lg border border-border bg-surface-1 p-4 transition-colors hover:border-brand hover:bg-sidebar-accent"
            >
              {content}
            </Link>
          ) : (
            <div
              key={c.title}
              aria-disabled="true"
              className="cursor-not-allowed rounded-lg border border-dashed border-border bg-surface-1 p-4 opacity-70"
            >
              {content}
            </div>
          );
        })}
      </div>
    </div>
  );
}
