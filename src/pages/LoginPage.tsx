import { KeyRound } from "lucide-react";
import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";

import { ButtonSpinner } from "../components/common/ButtonSpinner";
import { ErrorState } from "../components/common/ErrorState";
import { useAuth } from "../features/auth/AuthProvider";

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const from = (location.state as { from?: string } | null)?.from ?? "/rag/search";

  if (user) {
    return <Navigate to="/rag/search" replace />;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      await login(username, password);
      navigate(from, { replace: true });
    } catch (nextError) {
      setError(nextError);
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="login-shell">
      <form className="login-panel" onSubmit={handleSubmit}>
        <div className="login-brand">
          <div className="upload-icon">
            <KeyRound size={22} />
          </div>
          <div>
            <h1>RAG Console</h1>
            <p>登录后继续使用知识库。</p>
          </div>
        </div>

        {error ? <ErrorState title="登录失败" error={error} /> : null}

        <label className="form-field">
          <span>用户名</span>
          <input
            className="plain-input"
            value={username}
            onChange={(event) => setUsername(event.currentTarget.value)}
            autoComplete="username"
          />
        </label>
        <label className="form-field">
          <span>密码</span>
          <input
            className="plain-input"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.currentTarget.value)}
            autoComplete="current-password"
          />
        </label>

        <button className="button button-primary" type="submit" disabled={pending || !username.trim() || !password}>
          {pending ? <ButtonSpinner label="登录中" /> : <KeyRound size={16} />}
          {pending ? "登录中" : "登录"}
        </button>
      </form>
    </main>
  );
}
