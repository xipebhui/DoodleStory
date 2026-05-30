import { apiData, apiError, apiRouteError } from "@/lib/api-response";
import { requireApiProfile } from "@/lib/current-user";
import { prisma } from "@/lib/prisma";

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string; referenceId: string }> },
) {
  try {
    await requireApiProfile();
    const { id, referenceId } = await params;
    const reference = await prisma.styleReferenceImage.findFirst({
      where: { id: referenceId, styleId: id },
    });

    if (!reference) {
      return apiError("not_found", "参考图不存在", 404);
    }

    await prisma.styleReferenceImage.delete({ where: { id: referenceId } });
    return apiData({ deleted: true });
  } catch (error) {
    return apiRouteError(error);
  }
}
