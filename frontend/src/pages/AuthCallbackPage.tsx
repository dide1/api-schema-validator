import { useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { setToken } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export function AuthCallbackPage() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { refresh } = useAuth();
  const { showToast } = useToast();

  useEffect(() => {
    const token = params.get("token");
    const error = params.get("error");
    if (params.get("auth") === "disabled") {
      showToast("Authentication is disabled on this server", "info");
      navigate("/", { replace: true });
      return;
    }
    if (error) {
      showToast(`Authentication failed: ${error}`, "error");
      navigate("/login", { replace: true });
      return;
    }
    if (!token) {
      showToast("Authentication failed — no token received", "error");
      navigate("/login", { replace: true });
      return;
    }
    setToken(token);
    void refresh()
      .then(() => {
        void queryClient.invalidateQueries();
        const pendingInvite = localStorage.getItem("pendingInvite");
        if (pendingInvite) {
          localStorage.removeItem("pendingInvite");
          navigate(`/invites/${pendingInvite}`, { replace: true });
        } else {
          navigate("/", { replace: true });
        }
      })
      .catch(() => {
        showToast("Signed in but session could not be verified. Try again.", "error");
        navigate("/login", { replace: true });
      });
  }, [params, navigate, refresh, showToast, queryClient]);

  return <div className="page-center">Signing you in...</div>;
}
