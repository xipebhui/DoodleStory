import { Badge } from "@/components/ui/badge";

const taskLabels: Record<string, string> = {
  queued: "排队中",
  running: "生成中",
  succeeded: "已完成",
  partial_succeeded: "部分完成",
  failed: "失败",
  cancel_requested: "取消中",
  cancelled: "已取消",
  retrying: "重试中",
};

export function StatusBadge({ status }: { status: string }) {
  const tone =
    status === "succeeded" || status === "ready"
      ? "success"
      : status === "failed" || status === "cancelled"
        ? "danger"
        : status === "running" || status === "queued"
          ? "info"
          : "warning";

  return <Badge tone={tone}>{taskLabels[status] ?? status}</Badge>;
}
