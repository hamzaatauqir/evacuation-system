import { Navigate, Route, Routes } from "react-router-dom";
import { CwaHomePage } from "./pages/CwaHomePage";
import { NursesHomePage } from "./pages/NursesHomePage";
import { NursesRegisterPage } from "./pages/NursesRegisterPage";
import { NursesLoginPage } from "./pages/NursesLoginPage";
import { NursesForgotPasswordPage } from "./pages/NursesForgotPasswordPage";
import { NursesResetPasswordPage } from "./pages/NursesResetPasswordPage";
import { NursesPortalPage } from "./pages/NursesPortalPage";
import { NursesAccommodationPage } from "./pages/NursesAccommodationPage";
import { NursesComplaintPage } from "./pages/NursesComplaintPage";
import { NursesLeavingNoticePage } from "./pages/NursesLeavingNoticePage";
import { LegalOpfPage } from "./pages/LegalOpfPage";
import { DeathCasesPage } from "./pages/DeathCasesPage";
import { AdminCwaDashboard } from "./pages/AdminCwaDashboard";
import { AdminNursesPage } from "./pages/AdminNursesPage";
import { AdminLegalCasesPage } from "./pages/AdminLegalCasesPage";
import { AdminDeathCasesPage } from "./pages/AdminDeathCasesPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<CwaHomePage />} />
      <Route path="/nurses" element={<NursesHomePage />} />
      <Route path="/nurses/register" element={<NursesRegisterPage />} />
      <Route path="/nurses/login" element={<NursesLoginPage />} />
      <Route path="/nurses/forgot-password" element={<NursesForgotPasswordPage />} />
      <Route path="/nurses/reset-password" element={<NursesResetPasswordPage />} />
      <Route path="/nurses/portal" element={<NursesPortalPage />} />
      <Route path="/nurses/accommodation" element={<NursesAccommodationPage />} />
      <Route path="/nurses/complaint" element={<NursesComplaintPage />} />
      <Route path="/nurses/leaving-notice" element={<NursesLeavingNoticePage />} />
      <Route path="/legal-opf" element={<LegalOpfPage />} />
      <Route path="/death-cases" element={<DeathCasesPage />} />
      <Route path="/admin" element={<Navigate to="/admin/community-welfare" replace />} />
      <Route path="/admin/community-welfare" element={<AdminCwaDashboard />} />
      <Route path="/admin/nurses" element={<AdminNursesPage />} />
      <Route path="/admin/legal-cases" element={<AdminLegalCasesPage />} />
      <Route path="/admin/death-cases" element={<AdminDeathCasesPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
