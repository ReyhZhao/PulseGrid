import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, RequireAuth } from "./auth/AuthContext";
import Layout from "./components/Layout";
import AlertsPage from "./pages/AlertsPage";
import ChannelsPage from "./pages/ChannelsPage";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import MonitorDetailPage from "./pages/MonitorDetailPage";
import MonitorFormPage from "./pages/MonitorFormPage";

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
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
