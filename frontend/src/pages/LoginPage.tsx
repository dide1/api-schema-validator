import { useAuth } from "../context/AuthContext";

export function LoginPage() {
  const { login } = useAuth();

  return (
    <div className="page-center login-page">
      <div className="card login-card">
        <h1>Schema Validator</h1>
        <p>Sign in to manage and validate JSON schema templates.</p>
        <div className="login-actions">
          <button type="button" className="btn btn-primary" onClick={() => login("google")}>
            Sign in with Google
          </button>
          <button type="button" className="btn btn-secondary" onClick={() => login("github")}>
            Sign in with GitHub
          </button>
        </div>
      </div>
    </div>
  );
}
