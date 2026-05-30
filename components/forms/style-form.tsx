"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import type { Style } from "@/generated/prisma/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

export function StyleForm({ style }: { style?: Style }) {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();
  const isEdit = Boolean(style);

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        const payload = {
          name: String(formData.get("name") ?? ""),
          description: String(formData.get("description") ?? ""),
          status: String(formData.get("status") ?? "draft"),
          generationProfileKey: String(formData.get("generationProfileKey") ?? ""),
          stylePrompt: String(formData.get("stylePrompt") ?? ""),
        };

        startTransition(async () => {
          setMessage(null);
          const response = await fetch(isEdit ? `/api/v1/styles/${style?.id}` : "/api/v1/styles", {
            method: isEdit ? "PATCH" : "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify(payload),
          });
          const body = await response.json();

          if (!response.ok) {
            setMessage(body.error?.message ?? "保存失败");
            return;
          }

          router.push(`/styles/${body.data.id}`);
          router.refresh();
        });
      }}
    >
      <div className="grid gap-5 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="name">风格名称</Label>
          <Input id="name" name="name" defaultValue={style?.name ?? ""} required />
        </div>
        <div className="space-y-2">
          <Label htmlFor="status">状态</Label>
          <Select id="status" name="status" defaultValue={style?.status ?? "draft"}>
            <option value="draft">草稿</option>
            <option value="active">启用</option>
            <option value="disabled">停用</option>
          </Select>
        </div>
      </div>

      <div className="space-y-2">
        <Label htmlFor="generationProfileKey">生成配置 Key</Label>
        <Input
          id="generationProfileKey"
          name="generationProfileKey"
          defaultValue={style?.generationProfileKey ?? ""}
          placeholder="例如：sdxl-storybook-v1"
        />
        <p className="text-xs leading-5 text-slate-500">
          这里只保存后台生成配置的引用 Key，不暴露 Provider Key、模型 Key 或 API Key。
        </p>
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">描述</Label>
        <Textarea
          id="description"
          name="description"
          defaultValue={style?.description ?? ""}
          className="min-h-24"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="stylePrompt">风格提示词</Label>
        <Textarea id="stylePrompt" name="stylePrompt" defaultValue={style?.stylePrompt ?? ""} required />
      </div>

      {message ? <p className="text-sm text-red-600">{message}</p> : null}
      <Button type="submit" disabled={isPending}>
        {isEdit ? "保存风格" : "创建风格"}
      </Button>
    </form>
  );
}
