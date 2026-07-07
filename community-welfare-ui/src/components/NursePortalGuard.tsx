import type { ReactNode } from "react";
import { getNursePortalContext } from "../lib/nursePortal";
import { LoginRequired } from "./LoginRequired";

export function NursePortalGuard({ children, next }: { children: ReactNode; next: string }) {
  const ctx = getNursePortalContext();
  if (!ctx) return <LoginRequired next={next} />;
  return <>{children}</>;
}
