import Link from "next/link";
import { BookImage, Images, Settings, Sparkles } from "lucide-react";
import type { UserProfile } from "@/generated/prisma/client";

const navItems = [
  {
    href: "/tasks",
    label: "任务",
    icon: Images,
  },
  {
    href: "/styles",
    label: "风格",
    icon: Sparkles,
  },
  {
    href: "/settings",
    label: "设置",
    icon: Settings,
  },
];

export function AppShell({
  profile,
  children,
}: {
  profile: UserProfile;
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-slate-200/80 bg-white/70 px-4 py-5 backdrop-blur-xl lg:block">
        <Link href="/tasks" className="flex items-center gap-3 px-2">
          <span className="grid h-10 w-10 place-items-center rounded-md bg-slate-950 text-white">
            <BookImage className="h-5 w-5" aria-hidden="true" />
          </span>
          <span>
            <span className="block text-sm font-semibold text-slate-950">DoodleStory</span>
            <span className="block text-xs text-slate-500">故事生图工作台</span>
          </span>
        </Link>

        <nav className="mt-8 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-100 hover:text-slate-950"
            >
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="absolute bottom-5 left-4 right-4 rounded-lg border border-slate-200 bg-white p-3">
          <div className="text-sm font-medium text-slate-900">{profile.displayName ?? profile.email}</div>
          <div className="mt-1 text-xs text-slate-500">
            {profile.role === "admin" ? "管理员" : "普通用户"}
          </div>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-slate-200/80 bg-white/72 px-4 py-3 backdrop-blur-xl lg:hidden">
          <Link href="/tasks" className="flex items-center gap-2 font-semibold text-slate-950">
            <BookImage className="h-5 w-5" aria-hidden="true" />
            DoodleStory
          </Link>
          <nav className="mt-3 grid grid-cols-3 gap-2">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className="flex items-center justify-center gap-2 rounded-md bg-slate-100 px-3 py-2 text-xs font-medium text-slate-700"
              >
                <item.icon className="h-4 w-4" aria-hidden="true" />
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  );
}
