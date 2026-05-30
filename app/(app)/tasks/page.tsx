import Link from "next/link";
import { Plus } from "lucide-react";
import { EmptyState } from "@/components/app/empty-state";
import { StatusBadge } from "@/components/app/status-badge";
import { Button } from "@/components/ui/button";
import { prisma } from "@/lib/prisma";
import { requireCurrentProfile } from "@/lib/current-user";
import { formatDateTime, truncateText } from "@/lib/utils";

export default async function TasksPage() {
  const profile = await requireCurrentProfile();
  const where = profile.role === "admin" ? {} : { ownerUserId: profile.id };
  const tasks = await prisma.generationTask.findMany({
    where,
    include: {
      style: true,
      panels: {
        orderBy: { panelOrder: "asc" },
        take: 3,
      },
    },
    orderBy: { createdAt: "desc" },
    take: 50,
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-3xl font-semibold tracking-normal text-slate-950">任务</h1>
          <p className="mt-2 text-sm text-slate-500">管理故事切分、提示词生成和 9:16 图片结果。</p>
        </div>
        <Link href="/tasks/new">
          <Button type="button">
            <Plus className="h-4 w-4" aria-hidden="true" />
            新建任务
          </Button>
        </Link>
      </div>

      {tasks.length === 0 ? (
        <EmptyState
          title="还没有生成任务"
          description="先创建一个风格；图片 Provider 接入后，就可以把故事文本转成连续画面。"
          actionHref="/tasks/new"
          actionLabel="查看任务表单"
        />
      ) : (
        <div className="grid gap-4">
          {tasks.map((task) => (
            <Link
              key={task.id}
              href={`/tasks/${task.id}`}
              className="surface block rounded-lg p-5 transition hover:-translate-y-0.5 hover:border-slate-300"
            >
              <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-3">
                    <h2 className="text-lg font-semibold text-slate-950">{task.displayTitle}</h2>
                    <StatusBadge status={task.status} />
                  </div>
                  <p className="mt-2 text-sm leading-6 text-slate-500">{truncateText(task.originalText, 150)}</p>
                </div>
                <div className="shrink-0 text-sm text-slate-500">{formatDateTime(task.createdAt)}</div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
                <span className="rounded-full bg-slate-100 px-2.5 py-1">风格：{task.styleNameSnapshot}</span>
                <span className="rounded-full bg-slate-100 px-2.5 py-1">画面：{task.progressTotal || task.panels.length}</span>
                <span className="rounded-full bg-slate-100 px-2.5 py-1">
                  数量：{task.imageCountMode === "auto" ? "自动" : task.requestedImageCount}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
