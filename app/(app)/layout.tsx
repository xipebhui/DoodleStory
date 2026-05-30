import { AppShell } from "@/components/app/app-shell";
import { requireCurrentProfile } from "@/lib/current-user";

export const dynamic = "force-dynamic";

export default async function AuthenticatedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const profile = await requireCurrentProfile();

  return <AppShell profile={profile}>{children}</AppShell>;
}
