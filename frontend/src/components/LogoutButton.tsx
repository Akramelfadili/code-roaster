import type { JSX } from 'react/jsx-runtime';

interface LogoutButtonProps {
  onLogout: () => void;
}

export function LogoutButton({ onLogout }: LogoutButtonProps): JSX.Element {
  return (
    <button
      className="px-3 py-1.5 text-sm font-semibold text-gray-400 hover:text-white transition-colors"
      onClick={onLogout}
    >
      Logout
    </button>
  );
}
