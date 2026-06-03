import { BookOpenText, Database, FileSearch, FileText } from "lucide-react";
import { NavLink, Outlet } from "react-router-dom";

export function AppLayout() {
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
            文档
          </NavLink>
          <NavLink to="/rag/debug" className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}>
            <FileSearch size={18} />
            检索调试
          </NavLink>
          <NavLink to="/rag/synonyms" className={({ isActive }) => `nav-item ${isActive ? "nav-item-active" : ""}`}>
            <BookOpenText size={18} />
            检索词典
          </NavLink>
        </nav>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <span>知识库管理</span>
          <span className="runtime-pill">API /api/v1</span>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
