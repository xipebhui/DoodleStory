import Link from "next/link";
import { Button } from "@/components/ui/button";

export function EmptyState({
  title,
  description,
  actionHref,
  actionLabel,
}: {
  title: string;
  description: string;
  actionHref?: string;
  actionLabel?: string;
}) {
  return (
    <div className="surface flex min-h-72 flex-col items-center justify-center rounded-lg px-8 py-12 text-center">
      <h2 className="text-xl font-semibold text-slate-950">{title}</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500">{description}</p>
      {actionHref && actionLabel ? (
        <Link href={actionHref} className="mt-6">
          <Button type="button">{actionLabel}</Button>
        </Link>
      ) : null}
    </div>
  );
}
