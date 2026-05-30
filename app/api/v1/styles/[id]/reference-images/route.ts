import { apiData, apiError, apiRouteError } from "@/lib/api-response";
import { FileAssetPurpose } from "@/generated/prisma/client";
import { requireApiProfile } from "@/lib/current-user";
import { prisma } from "@/lib/prisma";
import { assertImageContentType, saveLocalFile, UnsupportedMediaTypeError } from "@/lib/storage/local-storage";

export async function POST(request: Request, { params }: { params: Promise<{ id: string }> }) {
  try {
    await requireApiProfile();
    const { id } = await params;
    const style = await prisma.style.findUnique({ where: { id } });

    if (!style) {
      return apiError("not_found", "风格不存在", 404);
    }

    const formData = await request.formData();
    const file = formData.get("file");

    if (!(file instanceof File)) {
      return apiError("bad_request", "必须上传参考图文件", 400);
    }

    assertImageContentType(file.type);
    const bytes = Buffer.from(await file.arrayBuffer());
    const stored = await saveLocalFile({
      purpose: "style_reference",
      bytes,
      filename: file.name,
    });
    const displayOrder = await prisma.styleReferenceImage.count({ where: { styleId: id } });
    const reference = await prisma.styleReferenceImage.create({
      data: {
        style: {
          connect: { id },
        },
        displayOrder,
        asset: {
          create: {
            purpose: FileAssetPurpose.style_reference,
            storageKey: stored.storageKey,
            originalFilename: file.name,
            contentType: file.type,
            byteSize: stored.byteSize,
            checksumSha256: stored.checksumSha256,
          },
        },
      },
      include: { asset: true },
    });

    return apiData(reference, { status: 201 });
  } catch (error) {
    if (error instanceof UnsupportedMediaTypeError) {
      return apiError("unsupported_media_type", error.message, 415);
    }

    return apiRouteError(error);
  }
}
