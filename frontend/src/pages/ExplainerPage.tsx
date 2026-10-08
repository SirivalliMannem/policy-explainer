import React, { useState, useEffect, useRef } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { Send, Sparkles, AlertCircle, ArrowRight, CornerDownLeft } from 'lucide-react';
import {
  PolicyDetail,
  PolicyContextCandidate,
  ChatMessage,
  QuestionAnswerResponse,
} from '../types';
import {
  createConversation,
  getConversation,
  setConversationContext,
  submitQuestion,
  searchPolicyContext,
  getPolicy,
} from '../services/api';
import { PolicyContextBanner } from '../components/explainer/PolicyContextBanner';
import {
  PolicyFeaturesPanel,
  PolicyFeatureTab,
} from '../components/explainer/PolicyFeaturesPanel';
import { ConversationStream } from '../components/explainer/ConversationStream';
import { AIProcessSidebar } from '../components/explainer/AIProcessSidebar';
import { PolicySelectModal } from '../components/explainer/PolicySelectModal';

export function ExplainerPage() {
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // Active Policy Context State
  const [activePolicy, setActivePolicy] = useState<PolicyContextCandidate | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);

  // Chat Conversation State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzingStepIndex, setAnalyzingStepIndex] = useState(0);

  // AI Process Panel State
  const [latestResult, setLatestResult] = useState<QuestionAnswerResponse | null>(null);

  // Policy Features Tab State
  const [activeFeatureTab, setActiveFeatureTab] = useState<PolicyFeatureTab>('overview');
  const [isFeaturesOpen, setIsFeaturesOpen] = useState(false);
  const [targetHighlight, setTargetHighlight] = useState<{
    type: 'coverage' | 'form';
    id: string;
  } | null>(null);

  // Policy Selector Modal
  const [isSelectModalOpen, setIsSelectModalOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Timer reference for thinking progression
  const thinkingTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Helper to format timestamp
  const getNowTime = () =>
    new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  // 1. Initial conversation initialization
  useEffect(() => {
    let isMounted = true;

    // Check if initial question or conversationId passed from dashboard
    const initialQuestion =
      location.state?.initialQuestion || searchParams.get('q') || null;
    const passedConvId =
      location.state?.conversationId || searchParams.get('conv') || null;

    if (passedConvId) {
      getConversation(passedConvId)
        .then((conv) => {
          if (!isMounted) return;
          setConversationId(conv.conversation_id);
          if (conv.policy_context) {
            setActivePolicy(conv.policy_context);
          }
          if (initialQuestion) {
            handleSendMessage(initialQuestion, conv.conversation_id, conv.policy_context);
          }
        })
        .catch(() => {
          // If conversation lookup fails, create new
          initNewConversation(initialQuestion);
        });
    } else {
      initNewConversation(initialQuestion);
    }

    return () => {
      isMounted = false;
      if (thinkingTimerRef.current) clearInterval(thinkingTimerRef.current);
    };
  }, []);

  const initNewConversation = async (autoQuestion?: string | null) => {
    try {
      const conv = await createConversation();
      setConversationId(conv.conversation_id);
      if (autoQuestion) {
        handleSendMessage(autoQuestion, conv.conversation_id, null);
      }
    } catch (err) {
      console.error('Failed to create conversation session:', err);
      setErrorMessage('Unable to initialize conversation session. Please verify backend connection.');
    }
  };

  // Automatic policy resolution helper from a free-text question
  const resolvePolicyFromQuestion = async (
    question: string
  ): Promise<PolicyContextCandidate | null> => {
    const qLower = question.toLowerCase();

    // Known customer names to check
    const knownNames = [
      'margaret chen',
      'priya raghavan',
      'elena moreau',
      'daniel ortiz',
      'james whitaker',
      'david chen',
      'chen',
    ];

    let matchTerm: string | null = null;
    for (const name of knownNames) {
      if (qLower.includes(name)) {
        matchTerm = name;
        break;
      }
    }

    // Known policy number patterns like HO-2847 or 2847
    if (!matchTerm) {
      const policyMatch = question.match(/(HO|PA)-\d{4}(-\d{4})?/i) || question.match(/\b\d{4}\b/);
      if (policyMatch) {
        matchTerm = policyMatch[0];
      }
    }

    if (!matchTerm) {
      return null;
    }

    try {
      const candidates = await searchPolicyContext(matchTerm);
      if (!candidates || candidates.length === 0) return null;

      // Filter by line of business if mentioned in query
      const isHomeowners =
        qLower.includes('water backup') ||
        qLower.includes('dwelling') ||
        qLower.includes('home') ||
        qLower.includes('roof') ||
        qLower.includes('sewer') ||
        qLower.includes('flood') ||
        qLower.includes('hail');

      const isAuto =
        qLower.includes('auto') ||
        qLower.includes('car') ||
        qLower.includes('collision') ||
        qLower.includes('driver') ||
        qLower.includes('vehicle');

      if (isHomeowners) {
        const hoMatch = candidates.find(
          (c) => c.line_of_business === 'homeowners' && c.status === 'in_force'
        );
        if (hoMatch) return hoMatch;
      } else if (isAuto) {
        const autoMatch = candidates.find(
          (c) => c.line_of_business === 'personal_auto' && c.status === 'in_force'
        );
        if (autoMatch) return autoMatch;
      }

      // Default to active in_force policy
      const inForcePolicy = candidates.find((c) => c.status === 'in_force') || candidates[0];
      return inForcePolicy;
    } catch (err) {
      console.warn('Policy resolution error:', err);
      return null;
    }
  };

  // Main submission handler
  const handleSendMessage = async (
    questionText: string,
    existingConvId?: string | null,
    currentPolicy?: PolicyContextCandidate | null
  ) => {
    const trimmed = questionText.trim();
    if (!trimmed || isAnalyzing) return;

    setErrorMessage(null);
    setInputValue('');

    const convId = existingConvId || conversationId;
    if (!convId) {
      setErrorMessage('Conversation session is not ready. Please refresh.');
      return;
    }

    let policyToUse = currentPolicy || activePolicy;

    // Add user message to stream
    const userMsg: ChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: trimmed,
      timestamp: getNowTime(),
    };
    setMessages((prev) => [...prev, userMsg]);

    // Start Thinking State
    setIsAnalyzing(true);
    setAnalyzingStepIndex(0);

    // Progression timer for smooth thinking state transitions
    if (thinkingTimerRef.current) clearInterval(thinkingTimerRef.current);
    thinkingTimerRef.current = setInterval(() => {
      setAnalyzingStepIndex((prev) => (prev < 4 ? prev + 1 : prev));
    }, 450);

    try {
      // If no active policy context yet, attempt automatic resolution
      if (!policyToUse) {
        const resolved = await resolvePolicyFromQuestion(trimmed);
        if (resolved) {
          policyToUse = resolved;
          setActivePolicy(resolved);
          await setConversationContext(convId, resolved.policy_id);
        } else {
          // Cannot resolve policy and no active context is present
          clearInterval(thinkingTimerRef.current!);
          setIsAnalyzing(false);

          const promptMsg: ChatMessage = {
            id: `assist-clarify-${Date.now()}`,
            sender: 'assistant',
            text:
              "To analyze policy wordings and coverage accurately, please specify which policyholder you are asking about (e.g. 'Does Margaret Chen have water backup coverage?'), or select a policy context below.",
            timestamp: getNowTime(),
            suggestedQuestions: [
              'Does Margaret Chen have water backup coverage?',
              'Does Elena Moreau have comprehensive auto coverage?',
              'Does Daniel Ortiz have collision coverage?',
            ],
          };
          setMessages((prev) => [...prev, promptMsg]);
          return;
        }
      }

      // Submit question to real backend API: POST /api/conversations/{convId}/questions
      const response = await submitQuestion(convId, trimmed);

      // Stop thinking animation
      if (thinkingTimerRef.current) clearInterval(thinkingTimerRef.current);
      setAnalyzingStepIndex(5);
      setIsAnalyzing(false);

      // Save latest result for AI Process rail
      setLatestResult(response);

      // Append assistant answer message
      const assistantMsg: ChatMessage = {
        id: `assist-${Date.now()}`,
        sender: 'assistant',
        text: response.answer,
        timestamp: getNowTime(),
        confidence: response.confidence,
        evidence: response.evidence,
        citations: response.citations,
        suggestedQuestions: response.suggested_questions,
        status: response.status,
        policyContext: response.policy_context,
      };

      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      if (thinkingTimerRef.current) clearInterval(thinkingTimerRef.current);
      setIsAnalyzing(false);
      console.error('Error submitting question to backend:', err);

      const errText =
        err?.data?.detail ||
        err?.message ||
        'Unable to answer question. Please verify connection to the Policy Explainer backend.';

      const errorMsg: ChatMessage = {
        id: `assist-err-${Date.now()}`,
        sender: 'assistant',
        text: `Error analyzing policy: ${errText}`,
        timestamp: getNowTime(),
        status: 'error',
      };
      setMessages((prev) => [...prev, errorMsg]);
    }
  };

  // Change Policy Selection Handler
  const handleSelectPolicy = async (candidate: PolicyContextCandidate) => {
    setActivePolicy(candidate);
    setIsFeaturesOpen(true); // Open features on explicit policy selection
    setTargetHighlight(null);

    if (conversationId) {
      try {
        await setConversationContext(conversationId, candidate.policy_id);
      } catch (err) {
        console.error('Failed to update conversation context:', err);
      }
    }
  };

  // Deep Link Action: View Coverage
  const handleViewCoverage = (coverageName: string) => {
    setIsFeaturesOpen(true);
    setActiveFeatureTab('coverages');
    setTargetHighlight({ type: 'coverage', id: coverageName });
  };

  // Deep Link Action: View Form
  const handleViewForm = (formNumber: string) => {
    setIsFeaturesOpen(true);
    setActiveFeatureTab('forms');
    setTargetHighlight({ type: 'form', id: formNumber });
  };

  return (
    <div className="flex flex-col h-[calc(100vh-6rem)] max-w-7xl mx-auto space-y-3.5">
      {/* 1. TOP: Policy Context Banner */}
      <PolicyContextBanner
        policy={activePolicy}
        onChangePolicyClick={() => setIsSelectModalOpen(true)}
      />

      {/* 2. SUB-TOP: Policy Features Area (Overview, Coverages, Forms, Claims, Billing) */}
      {activePolicy && (
        <PolicyFeaturesPanel
          policyId={activePolicy.policy_id}
          activeTab={activeFeatureTab}
          onTabChange={setActiveFeatureTab}
          targetHighlight={targetHighlight}
          isOpen={isFeaturesOpen}
          onToggleOpen={() => setIsFeaturesOpen(!isFeaturesOpen)}
        />
      )}

      {/* 3. MAIN WORKSPACE: Conversation Stream (Left) + AI Process Sidebar (Right) */}
      <div className="flex-1 min-h-0 flex flex-col lg:flex-row gap-3.5 overflow-hidden">
        {/* Left: Chat Stream Container */}
        <div className="flex-1 min-w-0 flex flex-col bg-white border border-[#E2E8F0] rounded-xl shadow-xs overflow-hidden">
          {errorMessage && (
            <div className="bg-red-50 border-b border-red-200 px-4 py-2 text-xs font-medium text-red-700 flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 text-red-500" />
              <span>{errorMessage}</span>
            </div>
          )}

          {/* Conversation Messages */}
          <ConversationStream
            messages={messages}
            isAnalyzing={isAnalyzing}
            analyzingStepIndex={analyzingStepIndex}
            onSelectSuggestion={(q) => handleSendMessage(q)}
            onViewCoverage={handleViewCoverage}
            onViewForm={handleViewForm}
          />

          {/* Bottom Chat Input Bar */}
          <div className="p-3 sm:p-4 border-t border-[#E2E8F0] bg-[#F8FAFC]">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage(inputValue);
              }}
              className="flex items-center gap-2"
            >
              <div className="relative flex-1">
                <input
                  type="text"
                  value={inputValue}
                  onChange={(e) => setInputValue(e.target.value)}
                  placeholder={
                    activePolicy
                      ? `Ask a question about ${activePolicy.customer_name}'s policy (e.g. "What is the deductible?")...`
                      : 'Ask any policy question (e.g. "Does Margaret Chen have water backup coverage?")...'
                  }
                  disabled={isAnalyzing}
                  className="w-full pl-4 pr-10 py-3 text-xs sm:text-sm rounded-xl border border-[#cbd5e1] bg-white text-[#0F2A43] placeholder-[#64748B] focus:border-[#F97316] focus:ring-2 focus:ring-[#F97316]/20 focus:outline-none transition-all disabled:opacity-60"
                />
                <span className="hidden sm:inline-flex items-center absolute right-3 top-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded text-[10px] font-mono text-slate-400 bg-slate-100 border border-slate-200">
                  <CornerDownLeft className="w-2.5 h-2.5 mr-0.5" /> Enter
                </span>
              </div>

              <button
                type="submit"
                disabled={!inputValue.trim() || isAnalyzing}
                className="inline-flex items-center justify-center px-4 sm:px-5 py-3 rounded-xl bg-[#EA580C] hover:bg-[#C2410C] text-white text-xs sm:text-sm font-semibold transition-all hover:shadow-[0_4px_12px_rgba(234,88,12,0.25)] active:translate-y-0 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
              >
                <span className="hidden sm:inline mr-1.5">Send</span>
                <Send className="w-4 h-4" />
              </button>
            </form>
          </div>
        </div>

        {/* Right: AI Process Panel (Desktop Rail / Collapsible) */}
        <div className="shrink-0 flex flex-col">
          <AIProcessSidebar
            isAnalyzing={isAnalyzing}
            stepIndex={analyzingStepIndex}
            latestResult={latestResult}
            policyNumber={activePolicy?.policy_number}
          />
        </div>
      </div>

      {/* Policy Selector Modal */}
      <PolicySelectModal
        isOpen={isSelectModalOpen}
        onClose={() => setIsSelectModalOpen(false)}
        onSelectPolicy={handleSelectPolicy}
        currentPolicyId={activePolicy?.policy_id}
      />
    </div>
  );
}

export default ExplainerPage;
