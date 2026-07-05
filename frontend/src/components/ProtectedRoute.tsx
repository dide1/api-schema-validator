import { useEffect, useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { apiRequest } from "../lib/api";

export function RequireAdmin() {
  const { user, isAdmin } = useAuth();
  if (!user) return null;
  return isAdmin ? <Outlet /> : <Navigate to="/" replace />;
}

export function RequireTeam() {
  const { user } = useAuth();
  if (!user) return null;
  return user.team_id ? <Outlet /> : <Navigate to="/" replace />;
}

export function ProtectedRoute() {
  const { user, loading, refresh } = useAuth();
  const [authEnabled, setAuthEnabled] = useState<boolean | null>(null);

  useEffect(() => {
    void apiRequest<{ enabled: boolean }>("/auth/config", { auth: false })
      .then((cfg) => {
        setAuthEnabled(cfg.enabled);
        if (!cfg.enabled) {
          void refresh();
        }
      })
      .catch(() => setAuthEnabled(true));
  }, [refresh]);

  if (loading || authEnabled === null) {
    return <div className="page-center">Loading...</div>;
  }

  if (!authEnabled) {
    return <Outlet />;
  }

  const token = localStorage.getItem("token");
  if (!token || !user) {
    return <Navigate to="/login" replace />;
  }

  return <Outlet />;
}
