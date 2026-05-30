import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { isAdminEmail } from "@/lib/env";
import { prisma } from "@/lib/prisma";
import type { UserProfile } from "@/generated/prisma/client";

export type SessionUserProfile = UserProfile;

export async function getSession() {
  return auth.api.getSession({
    headers: await headers(),
  });
}

export async function getCurrentProfile() {
  const session = await getSession();

  if (!session?.user?.email) {
    return null;
  }

  const email = session.user.email.toLowerCase();
  const role = isAdminEmail(email) ? "admin" : "user";

  return prisma.userProfile.upsert({
    where: {
      authUserId: session.user.id,
    },
    create: {
      authUserId: session.user.id,
      email,
      displayName: session.user.name ?? null,
      role,
    },
    update: {
      email,
      displayName: session.user.name ?? null,
      role,
    },
  });
}

export async function requireCurrentProfile() {
  const profile = await getCurrentProfile();

  if (!profile) {
    redirect("/login");
  }

  return profile;
}

export async function requireApiProfile() {
  const profile = await getCurrentProfile();

  if (!profile) {
    throw new ApiAuthError();
  }

  return profile;
}

export class ApiAuthError extends Error {
  constructor() {
    super("未登录或登录状态已失效");
    this.name = "ApiAuthError";
  }
}
