import { notFound } from "next/navigation";
import { ImageFrame } from "@/components/app/image-frame";
import { StatusBadge } from "@/components/app/status-badge";
import { Button } from "@/components/ui/button";
import { assertCanReadTask } from "@/lib/permissions";
import { prisma } from "@/lib/prisma";
import { requireCurrentProfile } from "@/lib/current-user";
import { formatDateTime } from "@/lib/utils";

export default async function TaskDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const profile = await requireCurrentProfile();
  const task = await prisma.generationTask.findUnique({
    where: { id },
    include: {
      panels: {
        include: {
          generatedImage: {
            include: { asset: true },
          },
        },
        orderBy: { panelOrder: "asc" },
      },
    },
  });

  if (!task) {
    notFound();
  }

  assertCanReadTask(profile, task);

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold text-slate-950">{task.displayTitle}</h1>
            <StatusBadge status={task.status} />
          </div>
          <p className="mt-2 text-sm text-slate-500">创建于 {formatDateTime(task.createdAt)}</p>
        </div>
        <Button type="button" disabled>
          下载全部图片
        </Button>
      </div>

      <section className="surface rounded-lg p-6">
        <h2 className="text-base font-semibold text-slate-950">原始故事</h2>
        <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-slate-600">{task.originalText}</p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {task.panels.length === 0 ? (
          <div className="surface rounded-lg p-6 text-sm text-slate-500">尚未生成 panel。</div>
        ) : (
          task.panels.map((panel) => (
            <article key={panel.id} className="surface rounded-lg p-3">
              <ImageFrame
                alt={`Panel ${panel.panelOrder + 1}`}
                src={
                  panel.generatedImage?.asset
                    ? `/api/v1/assets/${panel.generatedImage.asset.id}/content`
                    : null
                }
              />
              <div className="mt-3 space-y-2">
                <div className="text-xs font-medium text-slate-500">Panel {panel.panelOrder + 1}</div>
                <p className="text-sm leading-6 text-slate-700">{panel.originalTextSegment}</p>
              </div>
            </article>
          ))
        )}
      </section>
    </div>
  );
}
