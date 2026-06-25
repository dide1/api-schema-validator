import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, ApiError, type Visibility } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

export function EditTemplatePage() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const { isAdmin } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["schema", name],
    queryFn: () => api.getSchema(name!),
    enabled: !!name,
  });

  const [schemaText, setSchemaText] = useState<string | null>(null);
  const [visibility, setVisibility] = useState<Visibility | null>(null);
  const [teamId, setTeamId] = useState<string | null>(null);
  const [parseError, setParseError] = useState<string | null>(null);

  const currentText = schemaText ?? (data ? JSON.stringify(data.schema, null, 2) : "");
  const currentVisibility = visibility ?? data?.visibility ?? "private";
  const currentTeamId = teamId ?? data?.team_id ?? "";

  const updateMutation = useMutation({
    mutationFn: (payload: { schema: Record<string, unknown>; visibility?: Visibility; team_id?: string | null }) =>
      api.updateSchema(name!, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["schemas"] });
      void queryClient.invalidateQueries({ queryKey: ["schema", name] });
      showToast("Template updated", "success");
      navigate(`/templates/${name}`);
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Update failed", "error");
    },
  });

  const verifyMutation = useMutation({
    mutationFn: (schema: Record<string, unknown>) => api.verifySchema(schema),
    onSuccess: (result) => {
      showToast(result.valid ? "Schema is valid" : (result.message ?? "Invalid schema"), result.valid ? "success" : "error");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Verification failed", "error");
    },
  });

  if (isLoading) return <div className="page-center">Loading...</div>;
  if (error || !data) {
    return <div className="error-panel">{error instanceof ApiError ? error.message : "Not found"}</div>;
  }

  function parseSchema(): Record<string, unknown> | null {
    try {
      const parsed = JSON.parse(currentText) as Record<string, unknown>;
      setParseError(null);
      return parsed;
    } catch {
      setParseError("Invalid JSON syntax");
      return null;
    }
  }

  return (
    <div>
      <div className="page-header">
        <h1>Edit {data.schema_name}</h1>
      </div>

      <form
        className="form-card"
        onSubmit={(e) => {
          e.preventDefault();
          const schema = parseSchema();
          if (!schema) return;
          const payload: { schema: Record<string, unknown>; visibility?: Visibility; team_id?: string | null } = { schema };
          if (isAdmin) {
            payload.visibility = currentVisibility;
            if (currentVisibility === "team") payload.team_id = currentTeamId.trim() || null;
          }
          updateMutation.mutate(payload);
        }}
      >
        {isAdmin && (
          <>
            <label>
              Visibility
              <select
                value={currentVisibility}
                onChange={(e) => setVisibility(e.target.value as Visibility)}
              >
                <option value="private">Private</option>
                <option value="team">Team</option>
                <option value="public">Public</option>
              </select>
            </label>

            {currentVisibility === "team" && (
              <label>
                Team code
                <input
                  value={currentTeamId}
                  onChange={(e) => setTeamId(e.target.value)}
                  placeholder="e.g. payments"
                />
                <span className="field-hint">Only users assigned this team code can see this schema.</span>
              </label>
            )}
          </>
        )}

        <label>
          Schema JSON
          <textarea
            value={currentText}
            onChange={(e) => setSchemaText(e.target.value)}
            rows={18}
            className="code-input"
          />
        </label>
        {parseError && <div className="field-error">{parseError}</div>}

        <div className="form-actions">
          <button
            type="button"
            className="btn btn-secondary"
            onClick={() => {
              const schema = parseSchema();
              if (schema) verifyMutation.mutate(schema);
            }}
          >
            Verify schema
          </button>
          <button type="submit" className="btn btn-primary" disabled={updateMutation.isPending}>
            Save changes
          </button>
        </div>
      </form>
    </div>
  );
}
