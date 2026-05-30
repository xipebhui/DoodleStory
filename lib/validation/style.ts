import { z } from "zod";

export const styleStatusSchema = z.enum(["draft", "active", "disabled"]);

export const styleCreateSchema = z.object({
  name: z.string().trim().min(1, "风格名称不能为空").max(80, "风格名称不能超过 80 个字符"),
  description: z.string().trim().max(500, "风格描述不能超过 500 个字符").optional().nullable(),
  status: styleStatusSchema.default("draft"),
  generationProfileKey: z.string().trim().min(1, "生成配置 Key 不能为空").max(120).optional().nullable(),
  stylePrompt: z.string().trim().min(1, "风格提示词不能为空").max(8000),
});

export const styleUpdateSchema = styleCreateSchema.partial();
