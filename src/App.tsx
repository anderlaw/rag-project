import { Navigate, Route, Routes } from "react-router-dom";
import { Outlet, useLocation } from "react-router-dom";

import { LoadingState } from "./components/common/LoadingState";
import { AuthProvider, useAuth } from "./features/auth/AuthProvider";
import { AppLayout } from "./layouts/AppLayout";
import { DebugPage } from "./pages/DebugPage";
import { DocumentDetailPage } from "./pages/DocumentDetailPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { LoginPage } from "./pages/LoginPage";
import { QueryLogDetailPage } from "./pages/QueryLogDetailPage";
import { SearchPage } from "./pages/SearchPage";
import { SynonymsPage } from "./pages/SynonymsPage";

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route index element={<HomeRedirect />} />
            <Route path="/documents" element={<DocumentsPage />} />
            <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
            <Route path="/rag/search" element={<SearchPage />} />
            <Route element={<RequireSuperAdmin />}>
              <Route path="/rag/debug" element={<DebugPage />} />
              <Route path="/rag/synonyms" element={<SynonymsPage />} />
              <Route path="/rag/query-logs/:queryLogId" element={<QueryLogDetailPage />} />
            </Route>
            <Route path="*" element={<HomeRedirect />} />
          </Route>
        </Route>
      </Routes>
    </AuthProvider>
  );
}

function RequireAuth() {
  const { user, isLoading } = useAuth();
  const location = useLocation();
  if (isLoading) {
    return <LoadingState label="检查登录状态" />;
  }
  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

function RequireSuperAdmin() {
  const { user } = useAuth();
  if (user?.role !== "SUPER_ADMIN") {
    return <Navigate to="/rag/search" replace />;
  }
  return <Outlet />;
}

function HomeRedirect() {
  return <Navigate to="/rag/search" replace />;
}
