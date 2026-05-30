import { apiData, apiError, apiRouteError } from "@/lib/api-response";
import { requireApiProfile } from "@/lib/current-user";
import { assertCanReadTask } from "@/lib/permissions";
import { prisma } from "@/lib/prisma";

export async function POST(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const profile = await requireApiProfile();
    const { id } = await params;
    const task = await prisma.generationTask.findUnique({ where: { id } });

    if (!task) {
      return apiError("not_found", "任务不存在", 404);
    }

    assertCanReadTask(profile, task);

    if (!["queued", "running", "retrying"].includes(task.status)) {
      return apiError("conflict", "当前任务状态不允许取消", 409);
    }

    const updated = await prisma.generationTask.update({
      where: { id },
      data: {
        status: "cancel_requested",
        cancelRequestedAt: new Date(),
      },
    });

    return apiData(updated);
  } catch (error) {
    return apiRouteError(error);
  }
}
