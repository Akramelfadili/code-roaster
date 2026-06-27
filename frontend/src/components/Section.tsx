interface SectionProps {
  title: string;
  items: string[];
  icon: string;
}

export function Section({ title, items, icon }: SectionProps): JSX.Element | null {
  if (items.length === 0) return null;

  return (
    <div>
      <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-widest mb-2.5">
        {icon} {title}
      </h3>
      <ul className="space-y-2">
        {items.map((item, i) => (
          <li key={i} className="flex gap-2.5 text-sm text-gray-300 leading-snug">
            <span className="text-gray-600 shrink-0 mt-0.5">—</span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
