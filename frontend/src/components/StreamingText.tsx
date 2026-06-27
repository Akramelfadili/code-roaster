interface StreamingTextProps {
  text: string;
  isStreaming: boolean;
  isLoadingStructured: boolean;
}

function StatusDot({ active }: { active: boolean }): JSX.Element | null {
  if (!active) return null;
  return <span className="h-1.5 w-1.5 rounded-full bg-blue-400 animate-pulse" />;
}

function StreamingCursor({ visible }: { visible: boolean }): JSX.Element | null {
  if (!visible) return null;
  return (
    <span className="inline-block w-0.5 h-3.5 bg-blue-400 ml-0.5 align-middle animate-pulse" />
  );
}

function statusLabel(isStreaming: boolean, isLoadingStructured: boolean): string {
  if (isStreaming) return 'Streaming review…';
  if (isLoadingStructured) return 'Building structured report…';
  return 'Raw review';
}

export function StreamingText({
  text,
  isStreaming,
  isLoadingStructured,
}: StreamingTextProps): JSX.Element {
  const isActive = isStreaming || isLoadingStructured;

  return (
    <div className="border border-gray-800 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800">
        <span className="text-xs text-gray-500 uppercase tracking-widest">
          {statusLabel(isStreaming, isLoadingStructured)}
        </span>
        <StatusDot active={isActive} />
      </div>
      <div className="px-4 py-4 text-sm text-gray-300 font-mono leading-relaxed whitespace-pre-wrap max-h-96 overflow-y-auto">
        {text}
        <StreamingCursor visible={isStreaming} />
      </div>
    </div>
  );
}
