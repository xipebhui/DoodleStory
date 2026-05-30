import { ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export function ImageFrame({
  src,
  alt,
  className,
}: {
  src?: string | null;
  alt: string;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "relative aspect-[9/16] overflow-hidden rounded-md border border-slate-200 bg-slate-100",
        className,
      )}
    >
      {src ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={alt} className="h-full w-full object-cover" />
      ) : (
        <div className="flex h-full w-full items-center justify-center text-slate-400">
          <ImageIcon className="h-8 w-8" aria-hidden="true" />
        </div>
      )}
    </div>
  );
}
