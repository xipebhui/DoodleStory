import { apiData, apiRouteError, parsePagination } from "@/lib/api-response";
import { requireApiProfile } from "@/lib/current-user";
import { prisma } from "@/lib/prisma";
import { styleCreateSchema } from "@/lib/validation/style";

export async function GET(request: Request) {
  try {
    await requireApiProfile();
    const { skip, take, page, pageSize } = parsePagination(request.url);
    const [items, total] = await Promise.all([
      prisma.style.findMany({
        skip,
        take,
        orderBy: { updatedAt: "desc" },
        include: { referenceImages: true },
      }),
      prisma.style.count(),
    ]);

    return apiData({ items, page, pageSize, total });
  } catch (error) {
    return apiRouteError(error);
  }
}

export async function POST(request: Request) {
  try {
    await requireApiProfile();
    const payload = styleCreateSchema.parse(await request.json());
    const style = await prisma.style.create({
      data: {
        name: payload.name,
        description: payload.description || null,
        status: payload.status,
        generationProfileKey: payload.generationProfileKey || null,
        stylePrompt: payload.stylePrompt,
      },
    });

    return apiData(style, { status: 201 });
  } catch (error) {
    return apiRouteError(error);
  }
}
