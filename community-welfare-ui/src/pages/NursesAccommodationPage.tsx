import { Navigate } from "react-router-dom";
import { LoginRequired } from "../components/LoginRequired";
import { hasNursePortal } from "../lib/nursePortal";

export function NursesAccommodationPage() {
  if (!hasNursePortal()) return <LoginRequired next="accommodation" />;
  return <Navigate to="/nurses/portal?tab=stay" replace />;
}
