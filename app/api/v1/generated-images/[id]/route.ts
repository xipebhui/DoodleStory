import { apiData, apiError, apiRouteError } from "@/lib/api-response";
import { requireApiProfile } from "@/lib/current-user";
import { assertCanReadTask } from "@/lib/permissions";
import { prisma } from "@/lib/prisma";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const profile = await requireApiProfile();
    const { id } = await params;
    const image = await prisma.generatedImage.findUnique({
      where: { id },
      include: { asset: true, task: true, panel: true },
    });

    if (!image) {
      return apiError("not_found", "图片不存在", 404);
    }

    assertCanReadTask(profile, image.task);
    return apiData(image);
  } catch (error) {
    return apiRouteError(error);
  }
}
