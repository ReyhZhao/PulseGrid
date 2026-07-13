import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, RequireAuth, RequireStaff } from "./auth/AuthContext";
import Layout from "./components/Layout";
import AdminAuditPage from "./pages/admin/AdminAuditPage";
import AdminLayout from "./pages/admin/AdminLayout";
import AdminOrgsPage from "./pages/admin/AdminOrgsPage";
import AdminOverviewPage from "./pages/admin/AdminOverviewPage";
import AdminRegionsPage from "./pages/admin/AdminRegionsPage";
import AdminUsersPage from "./pages/admin/AdminUsersPage";
import AdminWorkersPage from "./pages/admin/AdminWorkersPage";
import AlertsPage from "./pages/AlertsPage";
import ChannelsPage from "./pages/ChannelsPage";
import DashboardPage from "./pages/DashboardPage";
import InviteAcceptPage from "./pages/InviteAcceptPage";
import LoginPage from "./pages/LoginPage";
import MonitorDetailPage from "./pages/MonitorDetailPage";
import MonitorFormPage from "./pages/MonitorFormPage";
import OnboardingPage from "./pages/OnboardingPage";
import OrgSettingsPage from "./pages/OrgSettingsPage";
import ProfilePage from "./pages/ProfilePage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchInterval: 30_000, staleTime: 10_000 },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/welcome"
              element={
                <RequireAuth>
                  <OnboardingPage />
                </RequireAuth>
              }
            />
            <Route
              path="/invite/:token"
              element={
                <RequireAuth>
                  <InviteAcceptPage />
                </RequireAuth>
              }
            />
            <Route
              element={
                <RequireAuth>
                  <Layout />
                </RequireAuth>
              }
            >
              <Route path="/" element={<DashboardPage />} />
              <Route path="/monitors/new" element={<MonitorFormPage />} />
              <Route path="/monitors/:id" element={<MonitorDetailPage />} />
              <Route path="/monitors/:id/edit" element={<MonitorFormPage />} />
              <Route path="/alerts" element={<AlertsPage />} />
              <Route path="/channels" element={<ChannelsPage />} />
              <Route path="/settings" element={<OrgSettingsPage />} />
              <Route path="/profile" element={<ProfilePage />} />
              <Route
                path="/admin"
                element={
                  <RequireStaff>
                    <AdminLayout />
                  </RequireStaff>
                }
              >
                <Route index element={<AdminOverviewPage />} />
                <Route path="workers" element={<AdminWorkersPage />} />
                <Route path="regions" element={<AdminRegionsPage />} />
                <Route path="orgs" element={<AdminOrgsPage />} />
                <Route path="users" element={<AdminUsersPage />} />
                <Route path="audit" element={<AdminAuditPage />} />
              </Route>
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
