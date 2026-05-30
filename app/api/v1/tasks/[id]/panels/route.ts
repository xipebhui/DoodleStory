import { apiData, apiError, apiRouteError } from "@/lib/api-response";
import { requireApiProfile } from "@/lib/current-user";
import { assertCanReadTask } from "@/lib/permissions";
import { prisma } from "@/lib/prisma";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const profile = await requireApiProfile();
    const { id } = await params;
    const task = await prisma.generationTask.findUnique({
      where: { id },
      include: {
        panels: {
          include: { generatedImage: { include: { asset: true } } },
          orderBy: { panelOrder: "asc" },
        },
      },
    });

    if (!task) {
      return apiError("not_found", "任务不存在", 404);
    }

    assertCanReadTask(profile, task);
    return apiData(task.panels);
  } catch (error) {
    return apiRouteError(error);
  }
}
