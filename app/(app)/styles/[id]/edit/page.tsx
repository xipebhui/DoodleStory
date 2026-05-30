import { notFound } from "next/navigation";
import { StyleForm } from "@/components/forms/style-form";
import { prisma } from "@/lib/prisma";

export default async function EditStylePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const style = await prisma.style.findUnique({ where: { id } });

  if (!style) {
    notFound();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-slate-950">编辑风格</h1>
        <p className="mt-2 text-sm text-slate-500">修改风格后，新任务会使用最新配置；历史任务保留快照。</p>
      </div>
      <section className="surface rounded-lg p-6">
        <StyleForm style={style} />
      </section>
    </div>
  );
}
