import { apiData, apiError, apiRouteError, parsePagination } from "@/lib/api-response";
import { requireApiProfile } from "@/lib/current-user";
import { isGenerationProviderConfigured } from "@/lib/env";
import { prisma } from "@/lib/prisma";
import { taskCreateSchema } from "@/lib/validation/task";

export async function GET(request: Request) {
  try {
    const profile = await requireApiProfile();
    const { skip, take, page, pageSize } = parsePagination(request.url);
    const where = profile.role === "admin" ? {} : { ownerUserId: profile.id };
    const [items, total] = await Promise.all([
      prisma.generationTask.findMany({
        where,
        skip,
        take,
        include: {
          panels: true,
          generatedImages: true,
        },
        orderBy: { createdAt: "desc" },
      }),
      prisma.generationTask.count({ where }),
    ]);

    return apiData({ items, page, pageSize, total });
  } catch (error) {
    return apiRouteError(error);
  }
}

export async function POST(request: Request) {
  try {
    await requireApiProfile();
    taskCreateSchema.parse(await request.json());

    if (!isGenerationProviderConfigured()) {
      return apiError(
        "provider_not_configured",
        "图片生成 Provider 尚未接入，暂不允许创建生成任务。",
        503,
      );
    }

    return apiError("provider_not_configured", "图片生成 Provider 尚未接入。", 503);
  } catch (error) {
    return apiRouteError(error);
  }
}
