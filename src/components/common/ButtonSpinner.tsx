type ButtonSpinnerProps = {
  label: string;
};

export function ButtonSpinner({ label }: ButtonSpinnerProps) {
  return <span className="button-spinner" role="status" aria-label={label} />;
}
