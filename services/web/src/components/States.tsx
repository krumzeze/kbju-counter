export function Spinner({ label = "Загрузка…" }: { label?: string }) {
  return (
    <div className="state">
      <div className="spinner" aria-hidden />
      <span className="muted">{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="state">
      <p>{message}</p>
      {onRetry && (
        <button className="btn" onClick={onRetry}>
          Повторить
        </button>
      )}
    </div>
  );
}
