import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, ApiError, type Visibility } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

const EMPTY_SCHEMA = `{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {}
}`;

export function UploadPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const [schemaName, setSchemaName] = useState("");
  const [schemaText, setSchemaText] = useState(EMPTY_SCHEMA);
  const [visibility, setVisibility] = useState<Visibility>("private");
  const [teamId, setTeamId] = useState(user?.team_id ?? "");
  const [parseError, setParseError] = useState<string | null>(null);

  const verifyMutation = useMutation({
    mutationFn: (schema: Record<string, unknown>) => api.verifySchema(schema),
    onSuccess: (result) => {
      if (result.valid) {
        showToast("Schema is valid", "success");
      } else {
        showToast(result.message ?? "Schema is invalid", "error");
      }
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Verification failed", "error");
    },
  });

  const uploadMutation = useMutation({
    mutationFn: (payload: {
      schema_name: string;
      schema: Record<string, unknown>;
      visibility: Visibility;
      team_id?: string | null;
    }) => api.uploadSchema(payload),
    onSuccess: (_data, variables) => {
      showToast("Template uploaded", "success");
      navigate(`/templates/${variables.schema_name}`);
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

  return (
    <div>
      <div className="page-header">
        <h1>Upload Template</h1>
      </div>

      <form
        className="form-card"
        onSubmit={(e) => {
          e.preventDefault();
          const schema = parseSchema();
          if (!schema || !schemaName.trim()) return;
          uploadMutation.mutate({
            schema_name: schemaName.trim(),
            schema,
            visibility,
            team_id: visibility === "team" ? (teamId.trim() || null) : null,
          });
        }}
      >
        <label>
          Schema name
          <input
            value={schemaName}
            onChange={(e) => setSchemaName(e.target.value)}
            pattern="[a-zA-Z0-9_-]+"
            required
            placeholder="my_schema"
          />
          <span className="field-hint">Letters, numbers, hyphens and underscores only — no spaces or dots (e.g. <code>user_profile</code>)</span>
        </label>

        <label>
          Visibility
          <select value={visibility} onChange={(e) => setVisibility(e.target.value as Visibility)}>
            <option value="private">Private</option>
            <option value="team">Team</option>
            <option value="public">Public</option>
          </select>
        </label>

        {visibility === "team" && (
          <label>
            Team code
            <input
              value={teamId}
              onChange={(e) => setTeamId(e.target.value)}
              placeholder="e.g. payments"
              required
            />
            <span className="field-hint">Only users assigned this team code can see this schema.</span>
          </label>
        )}

        <label>
          Schema JSON
          <textarea
            value={schemaText}
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
          <button type="submit" className="btn btn-primary" disabled={uploadMutation.isPending}>
            {uploadMutation.isPending ? "Uploading..." : "Upload"}
          </button>
        </div>
      </form>
    </div>
  );
}
