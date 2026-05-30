import Link from "next/link";
import { notFound } from "next/navigation";
import { ImageFrame } from "@/components/app/image-frame";
import { ReferenceImageUpload } from "@/components/forms/reference-image-upload";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { prisma } from "@/lib/prisma";
import { formatDateTime } from "@/lib/utils";

const statusLabel: Record<string, string> = {
  draft: "草稿",
  active: "启用",
  disabled: "停用",
};

export default async function StyleDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const style = await prisma.style.findUnique({
    where: { id },
    include: {
      referenceImages: {
        include: { asset: true },
        orderBy: [{ displayOrder: "asc" }, { createdAt: "asc" }],
      },
      styleTests: {
        orderBy: { createdAt: "desc" },
        take: 5,
      },
    },
  });

  if (!style) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="text-3xl font-semibold text-slate-950">{style.name}</h1>
            <Badge tone={style.status === "active" ? "success" : style.status === "disabled" ? "danger" : "neutral"}>
              {statusLabel[style.status]}
            </Badge>
          </div>
          <p className="mt-2 text-sm text-slate-500">更新于 {formatDateTime(style.updatedAt)}</p>
        </div>
        <Link href={`/styles/${style.id}/edit`}>
          <Button type="button" variant="secondary">
            编辑风格
          </Button>
        </Link>
      </div>

      <section className="surface rounded-lg p-6">
        <h2 className="text-base font-semibold text-slate-950">风格信息</h2>
        <dl className="mt-4 grid gap-4 md:grid-cols-2">
          <div>
            <dt className="text-xs font-medium text-slate-500">生成配置 Key</dt>
            <dd className="mt-1 text-sm text-slate-900">{style.generationProfileKey || "未配置"}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">最近测试</dt>
            <dd className="mt-1 text-sm text-slate-900">{formatDateTime(style.lastTestedAt)}</dd>
          </div>
        </dl>
        {style.description ? <p className="mt-5 text-sm leading-6 text-slate-600">{style.description}</p> : null}
      </section>

      <section className="surface rounded-lg p-6">
        <h2 className="text-base font-semibold text-slate-950">风格提示词</h2>
        <p className="mt-4 whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-sm leading-7 text-slate-700">
          {style.stylePrompt}
        </p>
      </section>

      <section className="surface rounded-lg p-6">
        <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
          <div>
            <h2 className="text-base font-semibold text-slate-950">参考图</h2>
            <p className="mt-1 text-sm text-slate-500">参考图用于风格调试和人工理解，上传后保存在本地磁盘。</p>
          </div>
        </div>
        <div className="mt-5">
          <ReferenceImageUpload styleId={style.id} />
        </div>
        <div className="mt-6 grid gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {style.referenceImages.map((reference) => (
            <ImageFrame
              key={reference.id}
              alt={reference.asset.originalFilename ?? "参考图"}
              src={`/api/v1/assets/${reference.asset.id}/content`}
            />
          ))}
        </div>
      </section>

      <section className="surface rounded-lg p-6">
        <h2 className="text-base font-semibold text-slate-950">风格测试</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          测试入口会复用风格提示词和生成配置 Key；当前 Provider 尚未接入，因此不开放提交。
        </p>
        <Button type="button" className="mt-4" disabled>
          创建测试
        </Button>
      </section>
    </div>
  );
}
