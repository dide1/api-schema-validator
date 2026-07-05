import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, ApiError, formatDate, type BatchValidateResultItem, type Visibility } from "../lib/api";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";

const EMPTY_PAYLOAD = `{
  "example": "value"
}`;

type SingleResult = { kind: "single"; valid: boolean; errors: { path: string; message: string }[]; suggestion?: string | null };
type BatchResult  = { kind: "batch";  results: BatchValidateResultItem[] };
type Result = SingleResult | BatchResult;

export function ValidatePage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const { showToast } = useToast();
  const queryClient = useQueryClient();

  const [schemaName, setSchemaName]   = useState(params.get("schema") ?? "");
  const [payloadText, setPayloadText] = useState(EMPTY_PAYLOAD);
  const [parseError, setParseError]   = useState<string | null>(null);
  const [result, setResult]           = useState<Result | null>(null);
  const [suggestion, setSuggestion]         = useState<string | null>(null);
  const [showSaveForm, setShowSaveForm]     = useState(false);
  const [saveName, setSaveName]             = useState("");
  const [saveVisibility, setSaveVisibility] = useState<Visibility>("private");
  const payloadFileRef = useRef<HTMLInputElement>(null);

  function loadPayloadFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      setPayloadText(reader.result as string);
      setParseError(null);
      setResult(null);
    };
    reader.readAsText(file);
    e.target.value = "";
  }

  const { data: schemas } = useQuery({
    queryKey: ["schemas", user?.id],
    queryFn: api.listSchemas,
    enabled: !!user,
  });

  const { data: savedPayloads } = useQuery({
    queryKey: ["payloads"],
    queryFn: api.listPayloads,
    enabled: !!user,
  });

  const singleMutation = useMutation({
    mutationFn: ({ schema_name, payload }: { schema_name: string; payload: Record<string, unknown> }) =>
      api.validateSingle(schema_name, payload),
    onSuccess: (data) => {
      setResult({ kind: "single", ...data });
      setSuggestion(null);
      if (data.valid) showToast("Payload is valid", "success");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Validation request failed", "error");
    },
  });

  const explainMutation = useMutation({
    mutationFn: ({ schema_name, payload }: { schema_name: string; payload: Record<string, unknown> }) =>
      api.validateSingle(schema_name, payload, true),
    onSuccess: (data) => {
      setSuggestion(data.suggestion ?? null);
    },
    onError: () => {
      showToast("AI explanation failed", "error");
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
      showToast(err instanceof ApiError ? err.message : "Validation request failed", "error");
    },
  });

  const saveMutation = useMutation({
    mutationFn: ({ name, content }: { name: string; content: Record<string, unknown> }) =>
      api.savePayload(name, content, saveVisibility, schemaName || null),
    onSuccess: (data) => {
      void queryClient.invalidateQueries({ queryKey: ["payloads"] });
      showToast(`Saved "${data.payload_name}"`, "success");
      setShowSaveForm(false);
      setSaveName("");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Failed to save payload", "error");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => api.deletePayload(name),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["payloads"] });
      showToast("Payload deleted", "success");
    },
    onError: (err: unknown) => {
      showToast(err instanceof ApiError ? err.message : "Failed to delete payload", "error");
    },
  });

  const isPending = singleMutation.isPending || batchMutation.isPending;

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
    setSuggestion(null);
    const parsed = tryParse();
    if (!parsed || !schemaName) return;
    if (Array.isArray(parsed)) {
      const bad = parsed.findIndex((item) => typeof item !== "object" || item === null || Array.isArray(item));
      if (bad !== -1) { setParseError(`Item at index ${bad} is not a JSON object`); return; }
      batchMutation.mutate({ schema_name: schemaName, payloads: parsed as Record<string, unknown>[] });
    } else {
      singleMutation.mutate({ schema_name: schemaName, payload: parsed });
    }
  }

  function handleSave() {
    if (!saveName.trim()) return;
    const parsed = tryParse();
    if (!parsed) return;
    const content: Record<string, unknown> = Array.isArray(parsed)
      ? { items: parsed }
      : (parsed as Record<string, unknown>);
    saveMutation.mutate({ name: saveName.trim(), content });
  }

  const myPayloads = (savedPayloads?.payloads ?? []).filter((p) => p.owner_id === user?.id);
  const otherPayloads = (savedPayloads?.payloads ?? []).filter((p) => p.owner_id !== user?.id);
  const hasSaved = myPayloads.length > 0 || otherPayloads.length > 0;

  // Compute allowed visibilities based on selected schema's visibility
  const schemaVis = (schemas?.templates ?? []).find((t) => t.schema_name === schemaName)?.visibility;
  const visRank: Record<string, number> = { private: 0, team: 1, public: 2 };
  const allowedVis: Visibility[] = (["private", "team", "public"] as Visibility[]).filter(
    (v) => !schemaVis || visRank[v] <= visRank[schemaVis],
  );

  // Clamp current saveVisibility if schema changes and makes it invalid
  const clampedSaveVis: Visibility = allowedVis.includes(saveVisibility)
    ? saveVisibility
    : (allowedVis[allowedVis.length - 1] ?? "private");

  return (
    <div>
      <div className="page-header">
        <h1>Validate Payload</h1>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: hasSaved ? "1fr 260px" : "1fr", gap: "1.5rem", alignItems: "start" }}>
        {/* ── Main form ── */}
        <div>
          <form
            className="form-card"
            onSubmit={(e) => { e.preventDefault(); handleValidate(); }}
          >
            <label>
              Schema
              <select
                value={schemaName}
                onChange={(e) => {
                  const next = e.target.value;
                  setSchemaName(next);
                  // Clamp visibility when schema changes
                  const nextSchemaVis = (schemas?.templates ?? []).find((t) => t.schema_name === next)?.visibility;
                  if (nextSchemaVis && visRank[saveVisibility] > visRank[nextSchemaVis]) {
                    setSaveVisibility(nextSchemaVis as Visibility);
                  }
                }}
                required
              >
                <option value="">Select a schema...</option>
                {(schemas?.schemas ?? []).map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </label>

            <input
              ref={payloadFileRef}
              type="file"
              accept=".json,application/json"
              style={{ display: "none" }}
              onChange={loadPayloadFile}
            />
            <div>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.375rem" }}>
                <label htmlFor="payload-json-input" style={{ margin: 0 }}>
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
                id="payload-json-input"
                value={payloadText}
                onChange={(e) => { setPayloadText(e.target.value); setResult(null); }}
                rows={14}
                className="code-input"
              />
            </div>
            {parseError && <div className="field-error">{parseError}</div>}

            <div className="form-actions">
              <button type="submit" className="btn btn-primary" disabled={isPending}>
                {isPending ? "Validating..." : "Validate"}
              </button>
              <button
                type="button"
                className="btn btn-secondary"
                onClick={() => { setShowSaveForm((v) => !v); setSaveName(""); }}
              >
                {showSaveForm ? "Cancel" : "Save payload"}
              </button>
            </div>

            {showSaveForm && (
              <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", alignItems: "flex-end", flexWrap: "wrap" }}>
                <label style={{ flex: 1, minWidth: 160, margin: 0 }}>
                  <span style={{ fontSize: "0.875rem", color: "var(--text-dim)", display: "block", marginBottom: "0.375rem" }}>Name</span>
                  <input
                    value={saveName}
                    onChange={(e) => setSaveName(e.target.value)}
                    placeholder="my-payload"
                    pattern="^[a-zA-Z0-9_-]+$"
                  />
                </label>
                <label style={{ margin: 0 }}>
                  <span style={{ fontSize: "0.875rem", color: "var(--text-dim)", display: "block", marginBottom: "0.375rem" }}>Visibility</span>
                  <select value={clampedSaveVis} onChange={(e) => setSaveVisibility(e.target.value as Visibility)}>
                    {allowedVis.map((v) => (
                      <option key={v} value={v}>{v.charAt(0).toUpperCase() + v.slice(1)}</option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!saveName.trim() || saveMutation.isPending}
                  onClick={handleSave}
                  style={{ alignSelf: "flex-end" }}
                >
                  {saveMutation.isPending ? "Saving..." : "Save"}
                </button>
              </div>
            )}
          </form>

          {result && result.kind === "single" && (
            <div className={`result-panel ${result.valid ? "result-valid" : "result-invalid"}`} style={{ marginTop: "1rem" }}>
              <h2>{result.valid ? "Valid" : "Invalid"}</h2>
              {!result.valid && (
                <>
                  <ul className="error-list">
                    {result.errors.map((err, i) => (
                      <li key={`${err.path}-${i}`}><strong>{err.path}</strong>: {err.message}</li>
                    ))}
                  </ul>
                  {suggestion ? (
                    <div style={{ marginTop: "0.875rem", padding: "0.75rem 1rem", background: "rgba(167,139,250,0.07)", border: "1px solid rgba(167,139,250,0.2)", borderLeft: "3px solid var(--accent)", borderRadius: "8px", color: "var(--text-h)", fontSize: "0.9rem", lineHeight: 1.65 }}>
                      <span style={{ display: "block", marginBottom: "0.4rem", fontSize: "0.7rem", fontFamily: "var(--mono)", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--accent)" }}>✦ ai suggestion</span>
                      {suggestion}
                    </div>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-sm"
                      style={{ marginTop: "0.75rem", borderColor: "var(--accent-border)", color: "var(--accent)", background: "var(--accent-dim)" }}
                      disabled={explainMutation.isPending}
                      onClick={() => {
                        const parsed = tryParse();
                        if (parsed && !Array.isArray(parsed)) explainMutation.mutate({ schema_name: schemaName, payload: parsed });
                      }}
                    >
                      {explainMutation.isPending ? "Explaining..." : "✦ Explain with AI"}
                    </button>
                  )}
                </>
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

        {/* ── Saved payloads sidebar ── */}
        {hasSaved && (
          <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            {myPayloads.length > 0 && (
              <div className="form-card" style={{ padding: "1rem" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-dim)", marginBottom: "0.75rem" }}>
                  My payloads
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
                  {myPayloads.map((p) => (
                    <div key={p.payload_name} style={{ display: "flex", alignItems: "center", gap: "0.375rem" }}>
                      <Link
                        to={`/payloads/${encodeURIComponent(p.payload_name)}`}
                        className="btn btn-ghost btn-sm"
                        style={{ flex: 1, justifyContent: "flex-start", fontFamily: "var(--mono)", fontSize: "0.8125rem", padding: "0.3rem 0.5rem", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                        title={p.updated_at ? formatDate(p.updated_at).full : p.payload_name}
                      >
                        {p.payload_name}
                      </Link>
                      <span className={`badge badge-${p.visibility}`} style={{ fontSize: "0.7rem", padding: "0.1rem 0.35rem", flexShrink: 0 }}>{p.visibility[0]}</span>
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        style={{ color: "var(--danger)", padding: "0.25rem 0.4rem", flexShrink: 0 }}
                        onClick={() => { if (window.confirm(`Delete "${p.payload_name}"?`)) deleteMutation.mutate(p.payload_name); }}
                        title="Delete"
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {otherPayloads.length > 0 && (
              <div className="form-card" style={{ padding: "1rem" }}>
                <div style={{ fontSize: "0.75rem", fontWeight: 600, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--text-dim)", marginBottom: "0.75rem" }}>
                  Shared payloads
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.375rem" }}>
                  {otherPayloads.map((p) => (
                    <Link
                      key={p.payload_name}
                      to={`/payloads/${encodeURIComponent(p.payload_name)}`}
                      className="btn btn-ghost btn-sm"
                      style={{ justifyContent: "flex-start", fontFamily: "var(--mono)", fontSize: "0.8125rem", padding: "0.3rem 0.5rem" }}
                      title={`by ${p.owner_name}`}
                    >
                      {p.payload_name}
                      <span style={{ marginLeft: "auto", fontSize: "0.7rem", color: "var(--text-dim)" }}>{p.owner_name}</span>
                    </Link>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
