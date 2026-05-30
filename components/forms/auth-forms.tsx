"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authClient } from "@/lib/auth-client";

function getErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }

  return "请求失败，请检查输入后重试";
}

export function LoginForm() {
  const router = useRouter();
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        const email = String(formData.get("email") ?? "");
        const password = String(formData.get("password") ?? "");

        startTransition(async () => {
          setMessage(null);
          try {
            const result = await authClient.signIn.email({
              email,
              password,
              callbackURL: "/tasks",
            });

            if (result.error) {
              setMessage(result.error.message ?? "登录失败");
              return;
            }

            router.push("/tasks");
            router.refresh();
          } catch (error) {
            setMessage(getErrorMessage(error));
          }
        });
      }}
    >
      <Field name="email" label="邮箱" type="email" autoComplete="email" />
      <Field name="password" label="密码" type="password" autoComplete="current-password" />
      {message ? <p className="text-sm text-red-600">{message}</p> : null}
      <Button type="submit" className="w-full" disabled={isPending}>
        登录
      </Button>
      <div className="flex items-center justify-between text-sm text-slate-500">
        <Link href="/register" className="hover:text-slate-950">
          注册账号
        </Link>
        <Link href="/forgot-password" className="hover:text-slate-950">
          忘记密码
        </Link>
      </div>
    </form>
  );
}

export function RegisterForm() {
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        const name = String(formData.get("name") ?? "");
        const email = String(formData.get("email") ?? "");
        const password = String(formData.get("password") ?? "");

        startTransition(async () => {
          setMessage(null);
          try {
            const result = await authClient.signUp.email({
              name,
              email,
              password,
              callbackURL: "/tasks",
            });

            if (result.error) {
              setMessage(result.error.message ?? "注册失败");
              return;
            }

            setMessage("注册成功，请查看服务端控制台中的邮箱验证链接。");
          } catch (error) {
            setMessage(getErrorMessage(error));
          }
        });
      }}
    >
      <Field name="name" label="昵称" autoComplete="name" />
      <Field name="email" label="邮箱" type="email" autoComplete="email" />
      <Field name="password" label="密码" type="password" autoComplete="new-password" />
      {message ? <p className="text-sm text-slate-600">{message}</p> : null}
      <Button type="submit" className="w-full" disabled={isPending}>
        创建账号
      </Button>
      <Link href="/login" className="block text-center text-sm text-slate-500 hover:text-slate-950">
        已有账号，去登录
      </Link>
    </form>
  );
}

export function ForgotPasswordForm() {
  const [message, setMessage] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const formData = new FormData(event.currentTarget);
        const email = String(formData.get("email") ?? "");

        startTransition(async () => {
          setMessage(null);
          try {
            const response = await fetch("/api/auth/request-password-reset", {
              method: "POST",
              headers: { "content-type": "application/json" },
              body: JSON.stringify({
                email,
                redirectTo: "/login",
              }),
            });

            if (!response.ok) {
              setMessage("重置请求失败，请确认邮箱是否正确。");
              return;
            }

            setMessage("如果邮箱存在，请查看服务端控制台中的重置链接。");
          } catch (error) {
            setMessage(getErrorMessage(error));
          }
        });
      }}
    >
      <Field name="email" label="邮箱" type="email" autoComplete="email" />
      {message ? <p className="text-sm text-slate-600">{message}</p> : null}
      <Button type="submit" className="w-full" disabled={isPending}>
        发送重置链接
      </Button>
      <Link href="/login" className="block text-center text-sm text-slate-500 hover:text-slate-950">
        返回登录
      </Link>
    </form>
  );
}

function Field({
  label,
  name,
  type = "text",
  autoComplete,
}: {
  label: string;
  name: string;
  type?: string;
  autoComplete?: string;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={name}>{label}</Label>
      <Input id={name} name={name} type={type} autoComplete={autoComplete} required />
    </div>
  );
}
