import { BookOpenText, Database, FileSearch, FileText, LogOut, Search } from "lucide-react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";

import { useAuth } from "../features/auth/AuthProvider";

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const isSuperAdmin = user?.role === "SUPER_ADMIN";

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <Database size={22} />
          <span>RAG Console</span>
        </div>
        <nav className="nav-list">
          <NavLink to="/documents" className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}>
            <FileText size={18} />
            文档管理
          </NavLink>
          <NavLink to="/rag/search" className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}>
            <Search size={18} />
            文档检索
          </NavLink>
          {isSuperAdmin ? (
            <>
              <NavLink to="/rag/debug" className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}>
                <FileSearch size={18} />
                检索调试
              </NavLink>
              <NavLink to="/rag/synonyms" className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}>
                <BookOpenText size={18} />
                检索词典
              </NavLink>
            </>
          ) : null}
        </nav>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>知识库管理</span>
          <div className="topbar-actions">
            <span className="runtime-pill">
              {user?.username ?? "-"} · {user?.role === "SUPER_ADMIN" ? "超管" : "普通用户"}
            </span>
            <button
              className="icon-button"
              type="button"
              aria-label="退出登录"
              onClick={() => {
                void logout().finally(() => navigate("/login", { replace: true }));
              }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
