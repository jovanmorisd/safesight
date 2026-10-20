import { Compass } from "lucide-react";
import { Link, Outlet, Route, Routes } from "react-router-dom";
import { Layout } from "./components/Layout";
import { EmptyState } from "./components/ui";
import { RequireAdmin, RequireAuth } from "./lib/auth";
import AuthPage, { ForgotPasswordPage, ResetPasswordPage } from "./pages/AuthPage";
import Dashboard from "./pages/Dashboard";
import InspectionDetail from "./pages/InspectionDetail";
import Inspections from "./pages/Inspections";
import Landing from "./pages/Landing";
import Models from "./pages/Models";
import Reports from "./pages/Reports";
import Review from "./pages/Review";
import Sites from "./pages/Sites";
import System from "./pages/System";
import UploadPage from "./pages/Upload";

function AppShell() {
  return (
    <RequireAuth>
      <Layout>
        <Outlet />
      </Layout>
    </RequireAuth>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<AuthPage mode="login" />} />
      <Route path="/register" element={<AuthPage mode="register" />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route element={<AppShell />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/inspections" element={<Inspections />} />
        <Route path="/inspections/:id" element={<InspectionDetail />} />
        <Route path="/review" element={<Review />} />
        <Route path="/reports" element={<Reports />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/sites" element={<Sites />} />
        <Route path="/system" element={<System />} />
        <Route
          path="/models"
          element={
            <RequireAdmin>
              <Models />
            </RequireAdmin>
          }
        />
        <Route
          path="*"
          element={
            <EmptyState
              icon={<Compass />}
              title="Page not found"
              action={
                <Link to="/dashboard" className="btn-primary">
                  Back to dashboard
                </Link>
              }
            />
          }
        />
      </Route>
    </Routes>
  );
}
