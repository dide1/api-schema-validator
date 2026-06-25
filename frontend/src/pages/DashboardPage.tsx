import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, formatDate, type Visibility } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

const EMPTY_SCHEMA = `{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {}
}`;

export function DashboardPage() {
  const { user, isAdmin } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const [showUpload, setShowUpload] = useState(false);
  const [schemaName, setSchemaName] = useState("");
  const [schemaText, setSchemaText] = useState(EMPTY_SCHEMA);
  const [visibility, setVisibility] = useState<Visibility>("private");
  const [teamId, setTeamId] = useState(user?.team_id ?? "");
  const [parseError, setParseError] = useState<string | null>(null);
  const schemaFileRef = useRef<HTMLInputElement>(null);

  function loadSchemaFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = reader.result as string;
      setSchemaText(text);
      setParseError(null);
      if (!schemaName.trim()) {
        setSchemaName(file.name.replace(/\.json$/i, "").replace(/[^a-zA-Z0-9_-]/g, "-"));
      }
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  const isViewer = !!user && user.role === "viewer";

  const { data, isLoading, isFetching, error } = useQuery({
    queryKey: ["schemas", user?.id],
    queryFn: api.listSchemas,
    enabled: !!user,
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => api.deleteSchema(name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["schemas"] });
      showToast("Template deleted", "success");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Delete failed", "error");
    },
  });

  const verifyMutation = useMutation({
    mutationFn: (schema: Record<string, unknown>) => api.verifySchema(schema),
    onSuccess: (result) => {
      showToast(result.valid ? "Schema is valid" : (result.message ?? "Schema is invalid"), result.valid ? "success" : "error");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Verification failed", "error");
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (payload: { schema_name: string; schema: Record<string, unknown>; visibility: Visibility; team_id?: string | null }) =>
      api.uploadSchema(payload),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: ["schemas"] });
      showToast(`"${variables.schema_name}" uploaded`, "success");
      setShowUpload(false);
      setSchemaName("");
      setSchemaText(EMPTY_SCHEMA);
      setVisibility("private");
      setParseError(null);
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Upload failed", "error");
    },
  });

  function parseSchema(): Record<string, unknown> | null {
    try {
      const parsed = JSON.parse(schemaText) as Record<string, unknown>;
      setParseError(null);
      return parsed;
    } catch {
      setParseError("Invalid JSON syntax");
      return null;
    }
  }

  if (!user || isLoading || isFetching) {
    return <div className="page-center">Loading templates...</div>;
  }
  if (error) {
    return (
      <div className="error-panel">
        {error instanceof ApiError ? error.message : "Failed to load templates"}
      </div>
    );
  }

  const templates = [...(data?.templates ?? [])].sort((a, b) => {
    if (!a.updated_at) return 1;
    if (!b.updated_at) return -1;
    return new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime();
  });

  return (
    <div>
      <div className="page-header">
        <h1>Schema Templates</h1>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setShowUpload((v) => !v)}
        >
          {showUpload ? "Cancel" : "Upload template"}
        </button>
      </div>

      {showUpload && (
        <form
          className="form-card"
          style={{ marginBottom: "1.5rem" }}
          onSubmit={(e) => {
            e.preventDefault();
            const schema = parseSchema();
            if (!schema || !schemaName.trim()) return;
            uploadMutation.mutate({
              schema_name: schemaName.trim(),
              schema,
              visibility: isViewer ? "private" : visibility,
              team_id: visibility === "team" ? (teamId.trim() || null) : null,
            });
          }}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 1.5rem" }}>
            <label>
              Schema name
              <input
                value={schemaName}
                onChange={(e) => setSchemaName(e.target.value)}
                pattern="[a-zA-Z0-9_-]+"
                required
                placeholder="my-schema"
                autoFocus
              />
              <span className="field-hint">Letters, numbers, hyphens, underscores — no spaces</span>
            </label>

            {!isViewer && (
              <label>
                Visibility
                <select value={visibility} onChange={(e) => setVisibility(e.target.value as Visibility)}>
                  <option value="private">Private</option>
                  <option value="team">Team</option>
                  <option value="public">Public</option>
                </select>
              </label>
            )}

            {!isViewer && visibility === "team" && (
              <label>
                Team code
                <input
                  value={teamId}
                  onChange={(e) => setTeamId(e.target.value)}
                  placeholder={user?.team_id ?? "e.g. payments"}
                  required
                />
                <span className="field-hint">Only users with this team code can see this schema.</span>
              </label>
            )}
          </div>

          <input
            ref={schemaFileRef}
            type="file"
            accept=".json,application/json"
            style={{ display: "none" }}
            onChange={loadSchemaFile}
          />
          <div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.375rem" }}>
              <label htmlFor="schema-json-input" style={{ margin: 0 }}>Schema JSON</label>
              <button
                type="button"
                className="btn btn-secondary btn-sm"
                onClick={() => schemaFileRef.current?.click()}
              >
                ↑ Load from file
              </button>
            </div>
            <textarea
              id="schema-json-input"
              value={schemaText}
              onChange={(e) => setSchemaText(e.target.value)}
              rows={14}
              className="code-input"
            />
          </div>
          {parseError && <div className="field-error">{parseError}</div>}

          <div className="form-actions">
            <button
              type="button"
              className="btn btn-secondary"
              onClick={() => { const s = parseSchema(); if (s) verifyMutation.mutate(s); }}
              disabled={verifyMutation.isPending}
            >
              Verify
            </button>
            <button type="submit" className="btn btn-primary" disabled={uploadMutation.isPending}>
              {uploadMutation.isPending ? "Uploading..." : "Upload"}
            </button>
          </div>
        </form>
      )}

      {templates.length === 0 ? (
        <div className="empty-state">No templates yet. Upload your first schema above.</div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Visibility</th>
              <th>Owner</th>
              <th>Updated</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {templates.map((t) => (
              <tr key={t.schema_name}>
                <td>
                  <Link to={`/templates/${t.schema_name}`}>{t.schema_name}</Link>
                </td>
                <td>
                  <span className={`badge badge-${t.visibility}`}>{t.visibility}</span>
                </td>
                <td>{t.owner_name}</td>
                <td>{t.updated_at ? (() => { const { label, full } = formatDate(t.updated_at); return <span title={full}>{label}</span>; })() : "—"}</td>
                <td className="actions">
                  <Link to={`/validate?schema=${t.schema_name}`} className="btn btn-sm">
                    Validate
                  </Link>
                  {(isAdmin || t.owner_id === user?.id) && (
                    <>
                      <Link to={`/templates/${t.schema_name}/edit`} className="btn btn-sm">
                        Edit
                      </Link>
                      <button
                        type="button"
                        className="btn btn-sm btn-danger"
                        onClick={() => {
                          if (window.confirm(`Delete "${t.schema_name}"?`)) {
                            deleteMutation.mutate(t.schema_name);
                          }
                        }}
                      >
                        Delete
                      </button>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
