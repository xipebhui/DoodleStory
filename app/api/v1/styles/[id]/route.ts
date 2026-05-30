import { apiData, apiError, apiRouteError } from "@/lib/api-response";
import { requireApiProfile } from "@/lib/current-user";
import { prisma } from "@/lib/prisma";
import { styleUpdateSchema } from "@/lib/validation/style";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    await requireApiProfile();
    const { id } = await params;
    const style = await prisma.style.findUnique({
      where: { id },
      include: {
        referenceImages: { include: { asset: true } },
      },
    });

    if (!style) {
      return apiError("not_found", "风格不存在", 404);
    }

    return apiData(style);
  } catch (error) {
    return apiRouteError(error);
  }
}

export async function PATCH(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    await requireApiProfile();
    const { id } = await params;
    const payload = styleUpdateSchema.parse(await request.json());
    const style = await prisma.style.update({
      where: { id },
      data: {
        ...(payload.name !== undefined ? { name: payload.name } : {}),
        ...(payload.description !== undefined ? { description: payload.description || null } : {}),
        ...(payload.status !== undefined ? { status: payload.status } : {}),
        ...(payload.generationProfileKey !== undefined
          ? { generationProfileKey: payload.generationProfileKey || null }
          : {}),
        ...(payload.stylePrompt !== undefined ? { stylePrompt: payload.stylePrompt } : {}),
      },
    });

    return apiData(style);
  } catch (error) {
    return apiRouteError(error);
  }
}

export async function DELETE(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    await requireApiProfile();
    const { id } = await params;
    const taskCount = await prisma.generationTask.count({ where: { styleId: id } });

    if (taskCount > 0) {
      return apiError("conflict", "已有任务引用该风格，不能删除", 409);
    }

    await prisma.style.delete({ where: { id } });
    return apiData({ deleted: true });
  } catch (error) {
    return apiRouteError(error);
  }
}
