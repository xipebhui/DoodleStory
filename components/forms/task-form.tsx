"use client";

import type { Style } from "@/generated/prisma/client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";

export function TaskForm({ styles }: { styles: Pick<Style, "id" | "name">[] }) {
  return (
    <form className="space-y-5">
      <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
        当前图片生成 Provider 尚未接入，任务创建入口只展示交互形态，提交按钮暂不可用。
      </div>
      <div className="space-y-2">
        <Label htmlFor="originalText">故事文本</Label>
        <Textarea id="originalText" name="originalText" disabled placeholder="用户原文会原样进入任务，不做改写。" />
      </div>
      <div className="grid gap-5 md:grid-cols-2">
        <div className="space-y-2">
          <Label htmlFor="imageCountMode">图片数量</Label>
          <Select id="imageCountMode" name="imageCountMode" disabled>
            <option value="auto">自动判断</option>
            <option value="fixed">固定数量</option>
          </Select>
        </div>
        <div className="space-y-2">
          <Label htmlFor="requestedImageCount">固定张数</Label>
          <Input id="requestedImageCount" name="requestedImageCount" type="number" min={1} max={80} disabled />
        </div>
      </div>
      <div className="space-y-2">
        <Label htmlFor="styleId">风格</Label>
        <Select id="styleId" name="styleId" disabled>
          {styles.length === 0 ? <option>暂无启用风格</option> : null}
          {styles.map((style) => (
            <option key={style.id} value={style.id}>
              {style.name}
            </option>
          ))}
        </Select>
      </div>
      <Button type="button" disabled>
        提交任务
      </Button>
    </form>
  );
}
