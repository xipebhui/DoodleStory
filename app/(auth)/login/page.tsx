import { LoginForm } from "@/components/forms/auth-forms";

export default function LoginPage() {
  return (
    <AuthPage title="登录 DoodleStory" description="进入你的故事生图工作台。">
      <LoginForm />
    </AuthPage>
  );
}

function AuthPage({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <main className="flex min-h-screen items-center justify-center px-4 py-12">
      <section className="surface w-full max-w-md rounded-lg p-8">
        <h1 className="text-2xl font-semibold text-slate-950">{title}</h1>
        <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p>
        <div className="mt-8">{children}</div>
      </section>
    </main>
  );
}
