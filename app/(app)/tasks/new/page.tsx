import { TaskForm } from "@/components/forms/task-form";
import { prisma } from "@/lib/prisma";

export default async function NewTaskPage() {
  const styles = await prisma.style.findMany({
    where: { status: "active" },
    select: { id: true, name: true },
    orderBy: { updatedAt: "desc" },
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-slate-950">新建任务</h1>
        <p className="mt-2 text-sm text-slate-500">故事文本会原样保存，再由后续流程切分为 panel。</p>
      </div>
      <section className="surface rounded-lg p-6">
        <TaskForm styles={styles} />
      </section>
    </div>
  );
}
