import type { FileAsset, UserProfile } from "@/generated/prisma/client";
import { prisma } from "@/lib/prisma";

export async function canReadAsset(profile: UserProfile, asset: FileAsset) {
  if (asset.purpose === "style_reference") {
    return true;
  }

  if (profile.role === "admin") {
    return true;
  }

  if (asset.purpose === "generated_image") {
    const image = await prisma.generatedImage.findFirst({
      where: {
        assetId: asset.id,
        task: {
          ownerUserId: profile.id,
        },
      },
      select: { id: true },
    });

    return Boolean(image);
  }

  if (asset.purpose === "download_archive") {
    const download = await prisma.taskDownload.findFirst({
      where: {
        assetId: asset.id,
        task: {
          ownerUserId: profile.id,
        },
      },
      select: { id: true },
    });

    return Boolean(download);
  }

  return false;
}
