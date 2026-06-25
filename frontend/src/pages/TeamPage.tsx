import { useQuery } from "@tanstack/react-query";
import { api, ApiError } from "../lib/api";
import { useAuth } from "../context/AuthContext";

export function TeamPage() {
  const { user } = useAuth();

  const { data, isLoading, error } = useQuery({
    queryKey: ["team-members", user?.team_id],
    queryFn: api.listTeamMembers,
    enabled: !!user?.team_id,
  });

  if (!user) return null;

  if (!user.team_id) {
    return (
      <div>
        <div className="page-header"><h1>Team</h1></div>
        <p className="field-hint">You are not a member of any team. Ask an admin to invite you.</p>
      </div>
    );
  }

  if (isLoading) return <div className="page-center">Loading team members...</div>;
  if (error) {
    return (
      <div className="error-panel">
        {error instanceof ApiError ? error.message : "Failed to load team members"}
      </div>
    );
  }

  const members = data?.members ?? [];

  return (
    <div>
      <div className="page-header">
        <h1>Team</h1>
        <span className="team-code-value">{user.team_id}</span>
      </div>

      <table className="data-table">
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.id}>
              <td>
                {m.name}
                {m.id === user.id && <span className="badge badge-self">you</span>}
              </td>
              <td>{m.email}</td>
              <td><span className="badge badge-role">{m.role}</span></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
