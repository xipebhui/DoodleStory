import { NextResponse } from "next/server";
import { apiError, apiRouteError } from "@/lib/api-response";
import { requireApiProfile } from "@/lib/current-user";
import { assertCanReadTask } from "@/lib/permissions";
import { prisma } from "@/lib/prisma";
import { readLocalFile } from "@/lib/storage/local-storage";

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    const profile = await requireApiProfile();
    const { id } = await params;
    const image = await prisma.generatedImage.findUnique({
      where: { id },
      include: { asset: true, task: true, panel: true },
    });

    if (!image || !image.asset) {
      return apiError("not_found", "图片不存在", 404);
    }

    assertCanReadTask(profile, image.task);
    const file = await readLocalFile(image.asset.storageKey);
    const extension = image.asset.contentType === "image/png" ? "png" : image.asset.contentType === "image/webp" ? "webp" : "jpg";

    return new NextResponse(file.bytes, {
      headers: {
        "content-type": image.asset.contentType,
        "content-length": String(file.byteSize),
        "content-disposition": `attachment; filename="panel-${image.panel.panelOrder + 1}.${extension}"`,
      },
    });
  } catch (error) {
    return apiRouteError(error);
  }
}
