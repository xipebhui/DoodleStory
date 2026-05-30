import { RegisterForm } from "@/components/forms/auth-forms";

export default function RegisterPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <section className="surface w-full max-w-md rounded-lg p-8">
        <h1 className="text-2xl font-semibold text-slate-950">创建账号</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          当前使用邮箱密码注册，验证链接会输出在开发服务控制台。
        </p>
        <div className="mt-8">
          <RegisterForm />
        </div>
      </section>
    </main>
  );
}
