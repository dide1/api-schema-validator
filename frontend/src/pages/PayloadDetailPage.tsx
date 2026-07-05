import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, useEffect } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { api, ApiError, type BatchValidateResultItem, type Visibility } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

type SingleResult = { kind: "single"; valid: boolean; errors: { path: string; message: string }[] };
type BatchResult  = { kind: "batch";  results: BatchValidateResultItem[] };
type Result = SingleResult | BatchResult;

const VIS_RANK: Record<string, number> = { private: 0, team: 1, public: 2 };
const ALL_VIS: Visibility[] = ["private", "team", "public"];

export function PayloadDetailPage() {
  const { name } = useParams<{ name: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const [schemaName, setSchemaName] = useState("");
  const [payloadText, setPayloadText] = useState("");
  const [visibility, setVisibility] = useState<Visibility>("private");
  const [parseError, setParseError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [dirty, setDirty] = useState(false);
  const payloadFileRef = useRef<HTMLInputElement>(null);

  function loadPayloadFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setPayloadText(reader.result as string);
      setParseError(null);
      setResult(null);
      setDirty(true);
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  const { data: payload, isLoading, error } = useQuery({
    queryKey: ["payload", name],
    queryFn: () => api.getPayload(name!),
    enabled: !!name,
  });

  const { data: schemas } = useQuery({
    queryKey: ["schemas", user?.id],
    queryFn: api.listSchemas,
    enabled: !!user,
  });

  useEffect(() => {
    if (payload) {
      setPayloadText(JSON.stringify(payload.content, null, 2));
      setVisibility(payload.visibility);
      // Pre-select the schema this payload was saved with, if it's still accessible
      if (payload.schema_name) setSchemaName(payload.schema_name);
      setDirty(false);
    }
  }, [payload]);

  // Determine allowed visibilities based on the saved schema's visibility
  const savedSchemaVis = payload?.schema_name
    ? (schemas?.templates ?? []).find((t) => t.schema_name === payload.schema_name)?.visibility
    : undefined;
  const allowedVis: Visibility[] = savedSchemaVis
    ? ALL_VIS.filter((v) => VIS_RANK[v] <= VIS_RANK[savedSchemaVis])
    : ALL_VIS;
  // Clamp if stored visibility somehow exceeds the cap
  const clampedVis: Visibility = allowedVis.includes(visibility)
    ? visibility
    : (allowedVis[allowedVis.length - 1] ?? "private");

  const singleMutation = useMutation({
    mutationFn: ({ schema_name, p }: { schema_name: string; p: Record<string, unknown> }) =>
      api.validateSingle(schema_name, p),
    onSuccess: (data) => {
      setResult({ kind: "single", ...data });
      if (data.valid) showToast("Payload is valid", "success");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Validation failed", "error");
    },
  });

  const batchMutation = useMutation({
    mutationFn: ({ schema_name, payloads }: { schema_name: string; payloads: Record<string, unknown>[] }) =>
      api.validateBatch(schema_name, payloads),
    onSuccess: (data) => {
      setResult({ kind: "batch", results: data.results });
      const allValid = data.results.every((r) => r.valid);
      if (allValid) showToast(`All ${data.results.length} payloads valid`, "success");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Validation failed", "error");
    },
  });

  const updateMutation = useMutation({
    mutationFn: (content: Record<string, unknown>) =>
      api.updatePayload(name!, content, clampedVis, payload?.schema_name ?? null),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["payload", name] });
      void queryClient.invalidateQueries({ queryKey: ["payloads"] });
      showToast("Payload saved", "success");
      setDirty(false);
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Save failed", "error");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: () => api.deletePayload(name!),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["payloads"] });
      showToast("Payload deleted", "success");
      navigate("/validate");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Delete failed", "error");
    },
  });

  function tryParse(): Record<string, unknown> | Record<string, unknown>[] | null {
    setParseError(null);
    try {
      return JSON.parse(payloadText) as Record<string, unknown> | Record<string, unknown>[];
    } catch {
      setParseError("Invalid JSON syntax");
      return null;
    }
  }

  function handleValidate() {
    const parsed = tryParse();
    if (!parsed || !schemaName) return;
    if (Array.isArray(parsed)) {
      const bad = parsed.findIndex((item) => typeof item !== "object" || item === null || Array.isArray(item));
      if (bad !== -1) { setParseError(`Item at index ${bad} is not a JSON object`); return; }
      batchMutation.mutate({ schema_name: schemaName, payloads: parsed as Record<string, unknown>[] });
    } else {
      singleMutation.mutate({ schema_name: schemaName, p: parsed });
    }
  }

  function handleSave() {
    const parsed = tryParse();
    if (!parsed) return;
    const content: Record<string, unknown> = Array.isArray(parsed)
      ? { items: parsed }
      : (parsed as Record<string, unknown>);
    updateMutation.mutate(content);
  }

  const isPending = singleMutation.isPending || batchMutation.isPending;
  const isOwner = !!payload && payload.owner_id === user?.id;

  if (isLoading) return <div className="page-center">Loading payload...</div>;
  if (error || !payload) {
    return (
      <div className="error-panel">
        {error instanceof ApiError ? error.message : "Payload not found"}
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <Link to="/validate" className="btn btn-ghost btn-sm" style={{ padding: "0.3rem 0.5rem" }}>
            ← Back
          </Link>
          <h1 style={{ fontFamily: "var(--mono)", fontSize: "1.25rem" }}>{name}</h1>
          <span className={`badge badge-${payload.visibility}`}>{payload.visibility}</span>
          {payload.schema_name && (
            <span style={{ fontSize: "0.8125rem", color: "var(--text-dim)", fontFamily: "var(--mono)" }}>
              · {payload.schema_name}
            </span>
          )}
        </div>
        {isOwner && (
          <button
            type="button"
            className="btn btn-sm btn-danger"
            onClick={() => { if (window.confirm(`Delete "${name}"?`)) deleteMutation.mutate(); }}
            disabled={deleteMutation.isPending}
          >
            Delete
          </button>
        )}
      </div>

      <form
        className="form-card"
        onSubmit={(e) => { e.preventDefault(); handleValidate(); }}
      >
        <label>
          Schema
          <select value={schemaName} onChange={(e) => setSchemaName(e.target.value)} required>
            <option value="">Select a schema...</option>
            {(schemas?.schemas ?? []).map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>

        {isOwner && (
          <label>
            Visibility
            {savedSchemaVis && savedSchemaVis !== "public" && (
              <span className="field-hint">
                Capped at <strong>{savedSchemaVis}</strong> — schema visibility limit.
              </span>
            )}
            <select
              value={clampedVis}
              onChange={(e) => { setVisibility(e.target.value as Visibility); setDirty(true); }}
            >
              {allowedVis.map((v) => (
                <option key={v} value={v}>{v.charAt(0).toUpperCase() + v.slice(1)}</option>
              ))}
            </select>
          </label>
        )}

        <input
          ref={payloadFileRef}
          type="file"
          accept=".json,application/json"
          style={{ display: "none" }}
          onChange={loadPayloadFile}
        />
        <div>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.375rem" }}>
            <label htmlFor="payload-detail-input" style={{ margin: 0 }}>
              Payload JSON
              <span className="field-hint" style={{ display: "inline", marginLeft: "0.5rem" }}>
                Single object <code>{"{}"}</code> or array <code>{"[{}, {}]"}</code> for batch.
              </span>
            </label>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              style={{ flexShrink: 0 }}
              onClick={() => payloadFileRef.current?.click()}
            >
              ↑ Load from file
            </button>
          </div>
          <textarea
            id="payload-detail-input"
            value={payloadText}
            onChange={(e) => { setPayloadText(e.target.value); setResult(null); setDirty(true); }}
            rows={18}
            className="code-input"
          />
        </div>
        {parseError && <div className="field-error">{parseError}</div>}

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={isPending}>
            {isPending ? "Validating..." : "Validate"}
          </button>
          {isOwner && (
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!dirty || updateMutation.isPending}
              onClick={handleSave}
            >
              {updateMutation.isPending ? "Saving..." : dirty ? "Save changes" : "Saved"}
            </button>
          )}
        </div>
      </form>

      {result && result.kind === "single" && (
        <div className={`result-panel ${result.valid ? "result-valid" : "result-invalid"}`} style={{ marginTop: "1rem" }}>
          <h2>{result.valid ? "Valid" : "Invalid"}</h2>
          {!result.valid && (
            <ul className="error-list">
              {result.errors.map((err, i) => (
                <li key={`${err.path}-${i}`}><strong>{err.path}</strong>: {err.message}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {result && result.kind === "batch" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem", marginTop: "1rem" }}>
          {result.results.map((item) => (
            <div key={item.index} className={`result-panel ${item.valid ? "result-valid" : "result-invalid"}`}>
              <h2>#{item.index + 1} — {item.valid ? "Valid" : "Invalid"}</h2>
              {!item.valid && (
                <ul className="error-list">
                  {item.errors.map((err, i) => (
                    <li key={`${err.path}-${i}`}><strong>{err.path}</strong>: {err.message}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
