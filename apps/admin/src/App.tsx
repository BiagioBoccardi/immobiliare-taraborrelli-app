import { Route, Routes } from "react-router-dom";

import { Layout } from "./components/Layout";
import { RequireAuth } from "./components/RequireAuth";
import { BulkPhotosPage } from "./pages/BulkPhotosPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ImportPage } from "./pages/ImportPage";
import { LeadDetailPage } from "./pages/LeadDetailPage";
import { LeadsPage } from "./pages/LeadsPage";
import { LoginPage } from "./pages/LoginPage";
import { OmiPage } from "./pages/OmiPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { PropertiesPage } from "./pages/PropertiesPage";
import { NewPropertyPage, PropertyEditPage } from "./pages/PropertyEditPage";
import { UsersPage } from "./pages/UsersPage";

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<DashboardPage />} />
        <Route path="leads" element={<LeadsPage />} />
        <Route path="leads/:id" element={<LeadDetailPage />} />
        <Route path="omi" element={<OmiPage />} />
        <Route path="properties" element={<PropertiesPage />} />
        <Route path="properties/new" element={<NewPropertyPage />} />
        <Route path="properties/import" element={<ImportPage />} />
        <Route path="properties/photos" element={<BulkPhotosPage />} />
        <Route path="properties/:id" element={<PropertyEditPage />} />
        <Route
          path="users"
          element={
            <RequireAuth adminOnly>
              <UsersPage />
            </RequireAuth>
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
