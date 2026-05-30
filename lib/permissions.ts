import type { GenerationTask, UserProfile } from "@/generated/prisma/client";

export function canReadTask(profile: UserProfile, task: Pick<GenerationTask, "ownerUserId">) {
  return profile.role === "admin" || task.ownerUserId === profile.id;
}

export function assertCanReadTask(
  profile: UserProfile,
  task: Pick<GenerationTask, "ownerUserId">,
) {
  if (!canReadTask(profile, task)) {
    throw new PermissionDeniedError();
  }
}

export class PermissionDeniedError extends Error {
  constructor() {
    super("没有权限访问该资源");
    this.name = "PermissionDeniedError";
  }
}
