import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, ApiError, formatDate } from "../lib/api";

export function TemplateDetailPage() {
  const { name } = useParams<{ name: string }>();

  const { data, isLoading, error } = useQuery({
    queryKey: ["schema", name],
    queryFn: () => api.getSchema(name!),
    enabled: !!name,
  });

  if (isLoading) return <div className="page-center">Loading...</div>;
  if (error || !data) {
    return (
      <div className="error-panel">
        {error instanceof ApiError ? error.message : "Template not found"}
      </div>
    );
  }

  return (
    <div>
      <div className="page-header">
        <h1>{data.schema_name}</h1>
        <Link to={`/templates/${data.schema_name}/edit`} className="btn btn-primary">
          Edit
        </Link>
      </div>
      <div className="meta-row">
        <span className={`badge badge-${data.visibility ?? "public"}`}>{data.visibility ?? "public"}</span>
        {data.updated_at && (() => { const { label, full } = formatDate(data.updated_at!); return <span title={full}>Updated {label}</span>; })()}
      </div>
      <pre className="code-block">{JSON.stringify(data.schema, null, 2)}</pre>
    </div>
  );
}
