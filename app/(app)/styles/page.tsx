import Link from "next/link";
import { Plus } from "lucide-react";
import { EmptyState } from "@/components/app/empty-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { prisma } from "@/lib/prisma";
import { formatDateTime, truncateText } from "@/lib/utils";

const statusLabel: Record<string, string> = {
  draft: "草稿",
  active: "启用",
  disabled: "停用",
};

export default async function StylesPage() {
  const styles = await prisma.style.findMany({
    include: {
      referenceImages: true,
      _count: {
        select: {
          tasks: true,
          styleTests: true,
        },
      },
    },
    orderBy: { updatedAt: "desc" },
  });

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <h1 className="text-3xl font-semibold text-slate-950">风格</h1>
          <p className="mt-2 text-sm text-slate-500">维护风格提示词、参考图和后台生成配置引用。</p>
        </div>
        <Link href="/styles/new">
          <Button type="button">
            <Plus className="h-4 w-4" aria-hidden="true" />
            新建风格
          </Button>
        </Link>
      </div>

      {styles.length === 0 ? (
        <EmptyState
          title="还没有风格"
          description="风格是任务生成图片时的核心约束，包含提示词、参考图和后台生成配置 Key。"
          actionHref="/styles/new"
          actionLabel="创建第一个风格"
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {styles.map((style) => (
            <Link
              key={style.id}
              href={`/styles/${style.id}`}
              className="surface block rounded-lg p-5 transition hover:-translate-y-0.5 hover:border-slate-300"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h2 className="text-lg font-semibold text-slate-950">{style.name}</h2>
                  <p className="mt-1 text-sm text-slate-500">更新于 {formatDateTime(style.updatedAt)}</p>
                </div>
                <Badge tone={style.status === "active" ? "success" : style.status === "disabled" ? "danger" : "neutral"}>
                  {statusLabel[style.status]}
                </Badge>
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-600">
                {style.description || truncateText(style.stylePrompt, 130)}
              </p>
              <div className="mt-4 flex flex-wrap gap-2 text-xs text-slate-500">
                <span className="rounded-full bg-slate-100 px-2.5 py-1">
                  参考图：{style.referenceImages.length}
                </span>
                <span className="rounded-full bg-slate-100 px-2.5 py-1">
                  任务：{style._count.tasks}
                </span>
                <span className="rounded-full bg-slate-100 px-2.5 py-1">
                  测试：{style._count.styleTests}
                </span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
