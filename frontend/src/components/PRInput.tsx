import type { JSX } from 'react/jsx-runtime';

interface PRInputProps {
  prUrl: string;
  isLoadingReview: boolean;
  onPrUrlChange: (prUrl: string) => void;
  onSubmit: () => void;
}

export function PRInput({
  prUrl,
  isLoadingReview,
  onPrUrlChange,
  onSubmit,
}: PRInputProps): JSX.Element {
  return (
    <div className="space-y-3">
      <input
        type="url"
        className="w-full bg-gray-900 border border-gray-800 rounded-lg px-4 py-3 text-sm font-mono text-gray-100 placeholder-gray-700 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-400"
        aria-label="Pull request URL"
        placeholder="https://github.com/owner/repo/pull/123"
        value={prUrl}
        onChange={(e) => onPrUrlChange(e.target.value)}
      />
      <button
        className="px-5 py-2 bg-blue-500 hover:bg-blue-400 disabled:bg-gray-800 disabled:text-gray-600 disabled:cursor-not-allowed text-sm font-semibold rounded-lg transition-colors"
        onClick={onSubmit}
        disabled={isLoadingReview || !prUrl.trim()}
      >
        {isLoadingReview ? 'Reviewing…' : 'Review PR'}
      </button>
    </div>
  );
}
