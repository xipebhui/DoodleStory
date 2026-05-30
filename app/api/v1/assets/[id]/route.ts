import { apiData, apiError, apiRouteError } from "@/lib/api-response";
import { canReadAsset } from "@/lib/asset-permissions";
import { requireApiProfile } from "@/lib/current-user";
import { prisma } from "@/lib/prisma";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const profile = await requireApiProfile();
    const { id } = await params;
    const asset = await prisma.fileAsset.findUnique({ where: { id } });

    if (!asset) {
      return apiError("not_found", "文件不存在", 404);
    }

    if (!(await canReadAsset(profile, asset))) {
      return apiError("forbidden", "没有权限访问该文件", 403);
    }

    return apiData(asset);
  } catch (error) {
    return apiRouteError(error);
  }
}
