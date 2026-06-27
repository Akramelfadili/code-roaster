import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';

import { StreamingText } from '@/components/StreamingText';

describe('StreamingText', () => {
  it('renders streaming text as it arrives', () => {
    render(
      <StreamingText
        text="Here is your code review result..."
        isStreaming={false}
        isLoadingStructured={false}
      />
    );
    expect(
      screen.getByText(/Here is your code review result\.\.\./)
    ).toBeInTheDocument();
  });

  it('shows "Streaming review…" label while streaming', () => {
    render(
      <StreamingText text="partial text" isStreaming isLoadingStructured={false} />
    );
    expect(screen.getByText('Streaming review…')).toBeInTheDocument();
  });

  it('shows "Building structured report…" label while loading structured data', () => {
    render(<StreamingText text="full text" isStreaming={false} isLoadingStructured />);
    expect(screen.getByText('Building structured report…')).toBeInTheDocument();
  });

  it('shows "Raw review" label when neither streaming nor loading', () => {
    render(
      <StreamingText
        text="completed text"
        isStreaming={false}
        isLoadingStructured={false}
      />
    );
    expect(screen.getByText('Raw review')).toBeInTheDocument();
  });

  it('prioritises the streaming label when both isStreaming and isLoadingStructured are true', () => {
    render(<StreamingText text="text" isStreaming isLoadingStructured />);
    expect(screen.getByText('Streaming review…')).toBeInTheDocument();
  });
});
