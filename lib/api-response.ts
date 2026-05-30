import { NextResponse } from "next/server";
import { ZodError } from "zod";
import { ApiAuthError } from "@/lib/current-user";
import { PermissionDeniedError } from "@/lib/permissions";

export type ApiErrorCode =
  | "bad_request"
  | "unauthorized"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "provider_not_configured"
  | "unsupported_media_type"
  | "internal_error";

export function apiData<T>(data: T, init?: ResponseInit) {
  return NextResponse.json({ data }, init);
}

export function apiError(code: ApiErrorCode, message: string, status: number) {
  return NextResponse.json(
    {
      error: {
        code,
        message,
      },
    },
    { status },
  );
}

export function apiRouteError(error: unknown) {
  if (error instanceof ApiAuthError) {
    return apiError("unauthorized", error.message, 401);
  }

  if (error instanceof PermissionDeniedError) {
    return apiError("forbidden", error.message, 403);
  }

  if (error instanceof ZodError) {
    return apiError("bad_request", error.issues[0]?.message ?? "请求参数不合法", 400);
  }

  console.error(error);
  return apiError("internal_error", "服务端处理失败", 500);
}

export function parsePagination(url: string) {
  const search = new URL(url).searchParams;
  const page = Math.max(1, Number(search.get("page") ?? 1));
  const pageSize = Math.min(100, Math.max(1, Number(search.get("pageSize") ?? 20)));

  return {
    page,
    pageSize,
    skip: (page - 1) * pageSize,
    take: pageSize,
  };
}
