import { z } from "zod";
import { apiData, apiError, apiRouteError } from "@/lib/api-response";
import { requireApiProfile } from "@/lib/current-user";
import { isGenerationProviderConfigured } from "@/lib/env";
import { prisma } from "@/lib/prisma";

const styleTestCreateSchema = z.object({
  testText: z.string().trim().min(1, "测试文本不能为空").max(2000),
});

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    await requireApiProfile();
    const { id } = await params;
    const tests = await prisma.styleTest.findMany({
      where: { styleId: id },
      include: { outputAsset: true },
      orderBy: { createdAt: "desc" },
      take: 50,
    });

    return apiData(tests);
  } catch (error) {
    return apiRouteError(error);
  }
}

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    await requireApiProfile();
    const { id } = await params;
    const payload = styleTestCreateSchema.parse(await request.json());
    const style = await prisma.style.findUnique({ where: { id } });

    if (!style) {
      return apiError("not_found", "风格不存在", 404);
    }

    if (!isGenerationProviderConfigured()) {
      return apiError("provider_not_configured", "图片生成 Provider 尚未接入，暂不允许创建风格测试。", 503);
    }

    return apiError(
      "provider_not_configured",
      `图片生成 Provider 尚未接入：${payload.testText}`,
      503,
    );
  } catch (error) {
    return apiRouteError(error);
  }
}
