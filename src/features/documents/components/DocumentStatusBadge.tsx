type DocumentStatusBadgeProps = {
  status: string;
};

export function DocumentStatusBadge({ status }: DocumentStatusBadgeProps) {
  const tone = status === "FAILED" ? "danger" : status === "PROCESSING" ? "warning" : "success";
  return <span className={`status-badge status-${tone}`}>{status}</span>;
}
