import { useLocation, useSearchParams } from 'react-router-dom';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Sparkles, ShieldCheck, ArrowRight, MessageSquareQuote } from 'lucide-react';
import { Badge } from '../components/ui/Badge';

export function ExplainerPage() {
  const location = useLocation();
  const [searchParams] = useSearchParams();

  // Read question passed from Dashboard "Ask about a policy" or Recent Questions
  const initialQuestion =
    location.state?.initialQuestion || searchParams.get('q') || null;
  const passedConversationId =
    location.state?.conversationId || searchParams.get('conv') || null;

  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h2 className="text-2xl font-display font-normal text-espresso tracking-tight">
            Policy Explainer
          </h2>
          <p className="text-sm font-sans text-muted-foreground mt-1">
            Grounded AI intelligence for complex insurance policy analysis.
          </p>
        </div>
        <Badge variant="primary" className="self-start sm:self-auto gap-1">
          <Sparkles className="h-3.5 w-3.5" /> Workspace Ready
        </Badge>
      </div>

      {initialQuestion && (
        <div className="rounded-xl border border-caramel/40 bg-surface-subtle p-5 shadow-card">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-card border border-caramel/30 text-caramel shrink-0 mt-0.5">
              <MessageSquareQuote className="h-5 w-5" />
            </div>
            <div className="flex-1">
              <span className="text-xs font-semibold text-espresso uppercase tracking-wider block">
                Question Dispatched from Dashboard
              </span>
              <p className="text-base font-medium text-foreground mt-1 italic">
                "{initialQuestion}"
              </p>
              <p className="text-xs text-muted-foreground mt-2 flex items-center gap-1.5">
                <span>Context resolution engine is primed to analyze this policy query in the forthcoming Explainer conversation stage.</span>
              </p>
            </div>
          </div>
        </div>
      )}

      {passedConversationId && !initialQuestion && (
        <div className="rounded-xl border border-caramel/40 bg-surface-subtle p-4 shadow-card">
          <span className="text-xs font-semibold text-espresso uppercase tracking-wider block">
            Recent Conversation Selected
          </span>
          <p className="text-xs font-mono text-muted-foreground mt-1">
            Session ID: {passedConversationId}
          </p>
        </div>
      )}

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-5 w-5 text-caramel" />
            <CardTitle>Policy Explainer Workspace Shell</CardTitle>
          </div>
          <CardDescription>
            Context resolution, question analysis, and grounded evidence workflow architecture.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            <div className="rounded-lg border border-border bg-surface-subtle p-4">
              <h4 className="text-sm font-semibold text-espresso mb-1">Architecture Flow:</h4>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Policy & Customer Context Selection → Question Submission → AI Retrieval & Grounding → Grounded Answer & Evidence Ledger Inspection → Suggested Follow-ups
              </p>
            </div>
            <div className="rounded-lg border border-dashed border-border bg-muted/40 p-8 text-center text-sm text-muted-foreground">
              Policy Explainer interactive workflow will be implemented in the specialized UI phase.
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default ExplainerPage;
