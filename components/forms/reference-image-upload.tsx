"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function ReferenceImageUpload({ styleId }: { styleId: string }) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);

        startTransition(async () => {
          setMessage(null);
          const response = await fetch(`/api/v1/styles/${styleId}/reference-images`, {
            method: "POST",
            body: formData,
          });
          const body = await response.json();

          if (!response.ok) {
            setMessage(body.error?.message ?? "上传失败");
            return;
          }

          router.refresh();
          event.currentTarget.reset();
        });
      }}
    >
      <Label htmlFor="file">参考图</Label>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Input id="file" name="file" type="file" accept="image/png,image/jpeg,image/webp" required />
        <Button type="submit" variant="secondary" disabled={isPending}>
          <Upload className="h-4 w-4" aria-hidden="true" />
          上传
        </Button>
      </div>
      {message ? <p className="text-sm text-red-600">{message}</p> : null}
    </form>
  );
}
