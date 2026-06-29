import { CodeInput } from '@/components/CodeInput';
import { ErrorMessage } from '@/components/ErrorMessage';
import { Header } from '@/components/Header';
import { ReviewResult } from '@/components/ReviewResult';
import { StreamingText } from '@/components/StreamingText';
import { useCodeForm } from '@/hooks/useCodeForm';
import { useReview } from '@/hooks/useReview';

export default function App(): JSX.Element {
  const {
    submitReview,
    streamingText,
    isStreaming,
    isLoadingStructured,
    reviewError,
    reviewResult,
  } = useReview();

  const { code, setCode, language, setLanguage, handleSubmit } =
    useCodeForm(submitReview);

  const isReviewInProgress = isStreaming || isLoadingStructured;
  const showStreamingText = streamingText.length > 0 && reviewResult === null;

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans">
      <Header />
      <main className="max-w-3xl mx-auto px-6 py-8 space-y-5">
        <CodeInput
          code={code}
          language={language}
          isLoadingReview={isReviewInProgress}
          onCodeChange={setCode}
          onLanguageChange={setLanguage}
          onSubmit={handleSubmit}
        />
        {reviewError && <ErrorMessage error={reviewError} onRetry={handleSubmit} />}
        {showStreamingText && (
          <StreamingText
            text={streamingText}
            isStreaming={isStreaming}
            isLoadingStructured={isLoadingStructured}
          />
        )}
        {reviewResult !== null && !isReviewInProgress && (
          <ReviewResult result={reviewResult} />
        )}
      </main>
    </div>
  );
}
