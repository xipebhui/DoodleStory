import path from "node:path";

export function requireEnv(name: string) {
  const value = process.env[name];

  if (!value) {
    throw new Error(`缺少必要环境变量：${name}`);
  }

  return value;
}

export function getStorageRoot() {
  const configured = process.env.DOODLESTORY_STORAGE_ROOT ?? "storage";

  if (path.isAbsolute(configured)) {
    return configured;
  }

  return path.join(/* turbopackIgnore: true */ process.cwd(), configured);
}

export function getAdminEmails() {
  return new Set(
    (process.env.ADMIN_EMAILS ?? "")
      .split(",")
      .map((email) => email.trim().toLowerCase())
      .filter(Boolean),
  );
}

export function isAdminEmail(email: string) {
  return getAdminEmails().has(email.trim().toLowerCase());
}

export function isGenerationProviderConfigured() {
  return false;
}
