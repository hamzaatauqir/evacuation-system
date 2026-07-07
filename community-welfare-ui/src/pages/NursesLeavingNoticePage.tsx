import { Navigate } from "react-router-dom";
import { LoginRequired } from "../components/LoginRequired";
import { hasNursePortal } from "../lib/nursePortal";

export function NursesLeavingNoticePage() {
  if (!hasNursePortal()) return <LoginRequired next="leaving" />;
  return <Navigate to="/nurses/portal?tab=leaving" replace />;
}
