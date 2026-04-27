import { Navigate } from "react-router-dom";
import { LoginRequired } from "../components/LoginRequired";
import { hasNursePortal } from "../lib/nursePortal";

export function NursesComplaintPage() {
  if (!hasNursePortal()) return <LoginRequired next="complaint" />;
  return <Navigate to="/nurses/portal?tab=complaint" replace />;
}
