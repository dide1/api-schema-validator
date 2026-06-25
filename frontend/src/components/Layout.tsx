import { Link, NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function Layout() {
  const { user, logout, isAdmin } = useAuth();

  return (
    <div className="app-shell">
      <header className="app-header">
        <Link to="/" className="brand">
          Schema Validator
        </Link>
        <nav className="nav">
          <NavLink to="/">Templates</NavLink>
          <NavLink to="/validate">Validate</NavLink>
          {isAdmin ? (
            <NavLink to="/admin">Admin</NavLink>
          ) : user?.team_id ? (
            <NavLink to="/team">Team</NavLink>
          ) : null}
          <NavLink to="/settings">Settings</NavLink>
        </nav>
        <div className="user-bar">
          {user && <span className="user-name">{user.name}</span>}
          {user && <span className="role-badge">{user.role}</span>}
          <button type="button" className="btn btn-ghost" onClick={logout}>
            Sign out
          </button>
        </div>
      </header>
      <main className="app-main">
        <Outlet />
      </main>
    </div>
  );
}
