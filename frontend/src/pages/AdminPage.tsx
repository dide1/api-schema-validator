import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type Invite } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

const ROLES = ["admin", "editor", "viewer"] as const;

function generateTeamCode(): string {
  const bytes = new Uint8Array(8);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

function copyText(text: string, onDone: () => void) {
  if (navigator.clipboard) {
    void navigator.clipboard.writeText(text).then(onDone);
  } else {
    const el = document.createElement("textarea");
    el.value = text;
    el.style.position = "fixed";
    el.style.opacity = "0";
    document.body.appendChild(el);
    el.select();
    document.execCommand("copy");
    document.body.removeChild(el);
    onDone();
  }
}

function InviteRow({ invite, onRevoke }: { invite: Invite; onRevoke: (token: string) => void }) {
  const [copied, setCopied] = useState(false);

  function copy() {
    copyText(invite.link ?? "", () => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const daysLeft = Math.ceil((new Date(invite.expires_at).getTime() - Date.now()) / 86_400_000);

  return (
    <tr>
      <td><code className="invite-link-cell">{invite.link}</code></td>
      <td>{daysLeft}d left</td>
      <td className="actions">
        <button type="button" className="btn btn-sm" onClick={copy}>
          {copied ? "Copied!" : "Copy"}
        </button>
        <button type="button" className="btn btn-sm btn-danger" onClick={() => onRevoke(invite.token)}>
          Revoke
        </button>
      </td>
    </tr>
  );
}

export function AdminPage() {
  const { user, refresh } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const [newInvite, setNewInvite] = useState<Invite | null>(null);
  const [copiedNew, setCopiedNew] = useState(false);
  const [teamInput, setTeamInput] = useState(user?.team_id ?? "");
  const [editingTeam, setEditingTeam] = useState(false);

  const { data: users, isLoading, error } = useQuery({
    queryKey: ["users", user?.id],
    queryFn: api.listUsers,
    enabled: !!user && user.role === "admin",
  });

  const { data: invites } = useQuery({
    queryKey: ["invites", user?.team_id],
    queryFn: api.listInvites,
    enabled: !!user && user.role === "admin" && !!user.team_id,
  });

  const updateMutation = useMutation({
    mutationFn: ({ userId, role, team_id }: { userId: string; role?: string; team_id?: string | null }) =>
      api.updateUser(userId, { role, team_id }),
    onSuccess: (_data, vars) => {
      void queryClient.invalidateQueries({ queryKey: ["users"] });
      if (vars.userId === user?.id) void refresh();
      showToast("User updated", "success");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Update failed", "error");
    },
  });

  const inviteMutation = useMutation({
    mutationFn: api.createInvite,
    onSuccess: (invite) => {
      setNewInvite(invite);
      void queryClient.invalidateQueries({ queryKey: ["invites"] });
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Failed to create invite", "error");
    },
  });

  const revokeMutation = useMutation({
    mutationFn: (token: string) => api.revokeInvite(token),
    onSuccess: (_data, token) => {
      void queryClient.invalidateQueries({ queryKey: ["invites"] });
      if (newInvite?.token === token) setNewInvite(null);
      showToast("Invite revoked", "success");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Failed to revoke invite", "error");
    },
  });

  const teamMutation = useMutation({
    mutationFn: (teamId: string) => api.updateMe({ team_id: teamId }),
    onSuccess: async (_data, code) => {
      await refresh();
      void queryClient.invalidateQueries({ queryKey: ["invites"] });
      setEditingTeam(false);
      setTeamInput(code);
      showToast("Team name updated", "success");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Failed to update team name", "error");
    },
  });

  function saveTeamCode(code: string) {
    teamMutation.mutate(code);
  }

  function copyNewLink() {
    if (!newInvite?.link) return;
    copyText(newInvite.link, () => {
      setCopiedNew(true);
      setTimeout(() => setCopiedNew(false), 2000);
    });
  }

  if (!user || isLoading) {
    return <div className="page-center">Loading users...</div>;
  }
  if (error) {
    return <div className="error-panel">{error instanceof ApiError ? error.message : "Failed to load users"}</div>;
  }

  return (
    <div>
      <div className="page-header">
        <h1>User Management</h1>
      </div>

      <div className="team-code-card">
        <div className="team-code-label">Your team</div>

        {!editingTeam ? (
          <div className="team-name-row">
            {user.team_id
              ? <><span className="team-code-value">{user.team_id}</span></>
              : <span className="team-code-hint">No team set yet.</span>}
            <button className="btn btn-sm" onClick={() => { setTeamInput(user.team_id ?? ""); setEditingTeam(true); }}>
              {user.team_id ? "Rename" : "Set name"}
            </button>
            <button className="btn btn-sm" onClick={() => saveTeamCode(generateTeamCode())} disabled={teamMutation.isPending}>
              {teamMutation.isPending ? "Saving..." : "Generate random"}
            </button>
          </div>
        ) : (
          <form className="team-name-form" onSubmit={(e) => { e.preventDefault(); if (teamInput.trim()) saveTeamCode(teamInput.trim()); }}>
            <input
              value={teamInput}
              onChange={(e) => setTeamInput(e.target.value)}
              placeholder="e.g. payments"
              autoFocus
            />
            <button type="submit" className="btn btn-sm btn-primary" disabled={teamMutation.isPending || !teamInput.trim()}>
              {teamMutation.isPending ? "Saving..." : "Save"}
            </button>
            <button type="button" className="btn btn-sm" onClick={() => setEditingTeam(false)}>Cancel</button>
          </form>
        )}

        {user.team_id && (
          <>
            <p className="team-code-hint" style={{ marginTop: "1rem" }}>
              Generate a link and share it in a group chat, Slack, or however you like. Anyone with the link can join your team.
            </p>
            <button
              className="btn btn-primary"
              onClick={() => inviteMutation.mutate()}
              disabled={inviteMutation.isPending}
            >
              {inviteMutation.isPending ? "Generating..." : "Generate invite link"}
            </button>

            {newInvite && (
              <div className="invite-result">
                <div className="invite-link-row">
                  <code className="invite-link">{newInvite.link}</code>
                  <button type="button" className="btn btn-sm btn-primary" onClick={copyNewLink}>
                    {copiedNew ? "Copied!" : "Copy"}
                  </button>
                </div>
                <p className="field-hint">Expires in 7 days. Anyone with this link can join your team.</p>
              </div>
            )}
          </>
        )}
      </div>

      {invites && invites.length > 0 && (
        <div className="settings-section" style={{ marginBottom: "2rem" }}>
          <h2>Pending invites</h2>
          <table className="data-table">
            <thead>
              <tr>
                <th>Link</th>
                <th>Expires</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {invites.map((inv) => (
                <InviteRow key={inv.token} invite={inv} onRevoke={(t) => revokeMutation.mutate(t)} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Team</th>
          </tr>
        </thead>
        <tbody>
          {(users ?? []).filter((u) => u.id === user.id || u.team_id === user.team_id).map((u) => {
            const isSelf = u.id === user.id;
            return (
              <tr key={u.id}>
                <td>
                  {u.name}
                  {isSelf && <span className="badge badge-self">you</span>}
                </td>
                <td>{u.email}</td>
                <td>
                  {isSelf ? (
                    <span className="badge badge-role">{u.role}</span>
                  ) : (
                    <select
                      className="role-select"
                      value={u.role}
                      disabled={updateMutation.isPending}
                      onChange={(e) => updateMutation.mutate({ userId: u.id, role: e.target.value })}
                    >
                      {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
                    </select>
                  )}
                </td>
                <td>
                  {isSelf ? (
                    <span className="team-status">{u.team_id ?? "—"}</span>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-sm btn-danger"
                      disabled={updateMutation.isPending}
                      onClick={() => updateMutation.mutate({ userId: u.id, team_id: "" })}
                    >
                      Remove from team
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
