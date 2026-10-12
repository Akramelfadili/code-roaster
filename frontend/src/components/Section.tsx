import type { JSX } from 'react/jsx-runtime';

import type { Finding } from '@/types/review';

function formatLineRange(lineStart: number, lineEnd: number | null): string {
  return lineEnd === null || lineEnd === lineStart
    ? `${lineStart}`
    : `${lineStart}-${lineEnd}`;
}

function formatFindingLocation({ file, lineStart, lineEnd }: Finding): string | null {
  if (lineStart === null) return file;
  const lineRange = formatLineRange(lineStart, lineEnd);
  return file === null ? `Line ${lineRange}` : `${file}:${lineRange}`;
}

interface FindingItemProps {
  finding: Finding;
}

function FindingItem({ finding }: FindingItemProps): JSX.Element {
  const location = formatFindingLocation(finding);

  return (
    <li className="flex gap-2.5 text-sm leading-snug">
      <span className="text-gray-600 shrink-0 mt-0.5">—</span>
      <div className="min-w-0 space-y-1">
        <p className="font-medium text-gray-200">{finding.title}</p>
        {location !== null && (
          <p className="font-mono text-xs text-blue-400 break-all">{location}</p>
        )}
        <p className="text-gray-400">{finding.explanation}</p>
      </div>
    </li>
  );
}

interface SectionProps {
  title: string;
  items: Finding[];
  icon: string;
}

export function Section({ title, items, icon }: SectionProps): JSX.Element | null {
  if (items.length === 0) return null;

  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-2.5">
        {icon} {title}
      </h3>
      <ul className="space-y-3">
        {items.map((finding) => (
          <FindingItem key={finding.id} finding={finding} />
        ))}
      </ul>
    </div>
  );
}
