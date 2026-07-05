import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export function SettingsPage() {
  const { user, logout } = useAuth();
  const { showToast } = useToast();
  const navigate = useNavigate();
  const [confirmDelete, setConfirmDelete] = useState(false);

  const deleteMutation = useMutation({
    mutationFn: api.deleteMe,
    onSuccess: () => {
      logout();
      navigate("/login", { replace: true });
      showToast("Account deleted", "success");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Failed to delete account", "error");
    },
  });

  if (!user) return null;

  return (
    <div>
      <div className="page-header">
        <h1>Settings</h1>
      </div>

      <div className="settings-section">
        <h2>Profile</h2>
        <dl className="settings-dl">
          <dt>Name</dt>
          <dd>{user.name}</dd>
          <dt>Email</dt>
          <dd>{user.email}</dd>
          <dt>Role</dt>
          <dd><span className="badge badge-role">{user.role}</span></dd>
        </dl>
      </div>

      {user.team_id && (
        <div className="settings-section">
          <h2>Team</h2>
          <dl className="settings-dl">
            <dt>Current team</dt>
            <dd><code>{user.team_id}</code></dd>
          </dl>
          <p className="field-hint">To leave this team, contact your admin or delete your account.</p>
        </div>
      )}

      <div className="settings-section settings-danger">
        <h2>Danger zone</h2>
        <p>Permanently delete your account. This cannot be undone.</p>
        {!confirmDelete ? (
          <button className="btn btn-danger" onClick={() => setConfirmDelete(true)}>
            Delete account
          </button>
        ) : (
          <div className="delete-confirm">
            <p><strong>Are you sure?</strong> Your account will be permanently removed.</p>
            <div className="delete-confirm-btns">
              <button
                className="btn btn-danger"
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? "Deleting..." : "Yes, delete my account"}
              </button>
              <button className="btn btn-secondary" onClick={() => setConfirmDelete(false)}>
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
