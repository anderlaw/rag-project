type ErrorStateProps = {
  title?: string;
  error: unknown;
  onRetry?: () => void;
};

export function ErrorState({ title = "加载失败", error, onRetry }: ErrorStateProps) {
  return (
    <div className="state-box state-box-error">
      <strong>{title}</strong>
      <span>{error instanceof Error ? error.message : "请求失败"}</span>
      {onRetry ? (
        <button className="button button-secondary" type="button" onClick={onRetry}>
          重试
        </button>
      ) : null}
    </div>
  );
}
