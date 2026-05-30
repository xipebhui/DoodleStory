import { StyleForm } from "@/components/forms/style-form";

export default function NewStylePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-slate-950">新建风格</h1>
        <p className="mt-2 text-sm text-slate-500">配置给任务使用的风格提示词和后台生成配置引用。</p>
      </div>
      <section className="surface rounded-lg p-6">
        <StyleForm />
      </section>
    </div>
  );
}
