import { SEVERITY_STYLES } from '@/constants/review';
import type { Severity } from '@/types/review';

interface SeverityBadgeProps {
  severity: Severity;
}

export function SeverityBadge({ severity }: SeverityBadgeProps): JSX.Element {
  return (
    <span
      className={`inline-block text-[11px] font-semibold uppercase tracking-widest px-2 py-0.5 rounded border ${SEVERITY_STYLES[severity]}`}
    >
      {severity}
    </span>
  );
}
