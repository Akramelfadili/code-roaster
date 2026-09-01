import { useState } from 'react';

import { CodeInput } from '@/components/CodeInput';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { ErrorMessage } from '@/components/ErrorMessage';
import { Header } from '@/components/Header';
import { PRReviewPanel } from '@/components/PRReviewPanel';
import { ReviewModeTabs } from '@/components/ReviewModeTabs';
import { ReviewResult } from '@/components/ReviewResult';
import { StreamingText } from '@/components/StreamingText';
import { useCodeForm } from '@/hooks/useCodeForm';
import { useGitHubAuth } from '@/hooks/useGitHubAuth';
import { useGitHubUser } from '@/hooks/useGitHubUser';
import { usePRForm } from '@/hooks/usePRForm';
import { usePRReview } from '@/hooks/usePRReview';
import { useReview } from '@/hooks/useReview';
import { ReviewMode } from '@/types/review';

export default function App(): JSX.Element {
  const [reviewMode, setReviewMode] = useState<ReviewMode>(ReviewMode.Code);

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

  const { githubToken, isAuthenticated, loginWithGitHub, logout } = useGitHubAuth();
  const { githubUser, gitHubUserError } = useGitHubUser(githubToken);
  const { submitPRReview, isLoadingPRReview, prReviewError, prReviewResult } =
    usePRReview();
  const {
    prUrl,
    setPrUrl,
    handleSubmit: handlePrSubmit,
  } = usePRForm(submitPRReview, githubToken);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 font-sans">
      <Header
        isAuthenticated={isAuthenticated}
        githubUser={githubUser}
        hasGitHubUserError={gitHubUserError !== null}
        onLogin={loginWithGitHub}
        onLogout={logout}
      />
      <main className="max-w-3xl mx-auto px-6 py-8 space-y-5">
        <ReviewModeTabs mode={reviewMode} onModeChange={setReviewMode} />
        {reviewMode === ReviewMode.Code ? (
          <div
            role="tabpanel"
            id="review-panel-code"
            aria-labelledby={`review-tab-${ReviewMode.Code}`}
          >
            <ErrorBoundary>
              <CodeInput
                code={code}
                language={language}
                isLoadingReview={isReviewInProgress}
                onCodeChange={setCode}
                onLanguageChange={setLanguage}
                onSubmit={handleSubmit}
              />
              {reviewError && (
                <ErrorMessage error={reviewError} onRetry={handleSubmit} />
              )}
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
            </ErrorBoundary>
          </div>
        ) : (
          <div
            role="tabpanel"
            id="review-panel-pr"
            aria-labelledby={`review-tab-${ReviewMode.PR}`}
          >
            <ErrorBoundary>
              <PRReviewPanel
                isAuthenticated={isAuthenticated}
                prUrl={prUrl}
                onPrUrlChange={setPrUrl}
                isLoadingReview={isLoadingPRReview}
                onSubmit={handlePrSubmit}
                reviewError={prReviewError}
                reviewResult={prReviewResult}
              />
            </ErrorBoundary>
          </div>
        )}
      </main>
    </div>
  );
}
