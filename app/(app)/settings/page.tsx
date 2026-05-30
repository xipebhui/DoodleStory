import { LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { requireCurrentProfile } from "@/lib/current-user";
import { getStorageRoot } from "@/lib/env";
import { formatDateTime } from "@/lib/utils";

export default async function SettingsPage() {
  const profile = await requireCurrentProfile();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-semibold text-slate-950">设置</h1>
        <p className="mt-2 text-sm text-slate-500">账户、权限和本地运行配置。</p>
      </div>

      <section className="surface rounded-lg p-6">
        <h2 className="text-base font-semibold text-slate-950">当前用户</h2>
        <dl className="mt-5 grid gap-4 md:grid-cols-2">
          <div>
            <dt className="text-xs font-medium text-slate-500">邮箱</dt>
            <dd className="mt-1 text-sm text-slate-900">{profile.email}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">角色</dt>
            <dd className="mt-1 text-sm text-slate-900">{profile.role === "admin" ? "管理员" : "普通用户"}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">创建时间</dt>
            <dd className="mt-1 text-sm text-slate-900">{formatDateTime(profile.createdAt)}</dd>
          </div>
          <div>
            <dt className="text-xs font-medium text-slate-500">本地文件目录</dt>
            <dd className="mt-1 break-all text-sm text-slate-900">{getStorageRoot()}</dd>
          </div>
        </dl>
      </section>

      <section className="surface rounded-lg p-6">
        <h2 className="text-base font-semibold text-slate-950">生成能力</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          图片生成 Provider 尚未接入。风格可以维护，但任务创建和风格测试会返回明确错误。
        </p>
      </section>

      <form action="/api/auth/sign-out" method="post">
        <Button type="submit" variant="secondary">
          <LogOut className="h-4 w-4" aria-hidden="true" />
          退出登录
        </Button>
      </form>
    </div>
  );
}
