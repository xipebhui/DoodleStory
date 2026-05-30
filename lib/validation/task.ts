import { z } from "zod";

export const taskCreateSchema = z.object({
  originalText: z.string().trim().min(1, "故事文本不能为空").max(20000),
  imageCountMode: z.enum(["auto", "fixed"]),
  requestedImageCount: z.number().int().min(1).max(80).optional().nullable(),
  styleId: z.string().min(1, "必须选择风格"),
});
