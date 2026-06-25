import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError, formatDate, type Invite } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export function AcceptInvitePage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { user, loading, login, refresh } = useAuth();
  const { showToast } = useToast();
  const [invite, setInvite] = useState<Invite | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [accepting, setAccepting] = useState(false);

  useEffect(() => {
    if (!token) return;
    api.getInvite(token).then(setInvite).catch((err: unknown) => {
      setFetchError(err instanceof ApiError ? err.message : "Invalid or expired invite link.");
    });
  }, [token]);

  function handleSignIn(provider: "google" | "github") {
    localStorage.setItem("pendingInvite", token!);
    login(provider);
  }

  async function handleAccept() {
    if (!token) return;
    setAccepting(true);
    try {
      await api.acceptInvite(token);
      await refresh();
      showToast("You've joined the team!", "success");
      navigate("/", { replace: true });
    } catch (err) {
      showToast(err instanceof ApiError ? err.message : "Failed to accept invite", "error");
      setAccepting(false);
    }
  }

  if (loading) return <div className="page-center">Loading...</div>;

  if (fetchError) {
    return (
      <div className="invite-page">
        <div className="invite-card">
          <div className="invite-icon">✕</div>
          <h1>Invalid invite</h1>
          <p>{fetchError}</p>
          <button className="btn btn-primary" onClick={() => navigate("/")}>Go to dashboard</button>
        </div>
      </div>
    );
  }

  if (!invite) return <div className="page-center">Loading invite...</div>;

  return (
    <div className="invite-page">
      <div className="invite-card">
        <div className="invite-icon">✉</div>
        <h1>You've been invited</h1>
        <p>You've been invited to join team <strong>{invite.team_id}</strong>.</p>
        <p className="invite-expiry">
          Expires {formatDate(invite.expires_at).label}
        </p>

        {user ? (
          user.team_id === invite.team_id ? (
            <>
              <p className="invite-note">You're already on this team.</p>
              <button className="btn btn-primary" onClick={() => navigate("/")}>Go to dashboard</button>
            </>
          ) : (
            <button className="btn btn-primary" onClick={handleAccept} disabled={accepting}>
              {accepting ? "Joining..." : "Accept & join team"}
            </button>
          )
        ) : (
          <>
            <p className="invite-note">Sign in to accept this invite.</p>
            <div className="invite-login-btns">
              <button className="btn btn-primary" onClick={() => handleSignIn("google")}>
                Sign in with Google
              </button>
              <button className="btn btn-secondary" onClick={() => handleSignIn("github")}>
                Sign in with GitHub
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
