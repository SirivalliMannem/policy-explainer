import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { HelpCircle } from 'lucide-react';

export function HelpPage() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-navy tracking-tight">Help & Documentation</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Policy Explainer operational guide and references.
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <HelpCircle className="h-5 w-5 text-primary" />
            <CardTitle>Help & Resources Shell</CardTitle>
          </div>
          <CardDescription>
            Placeholder destination for support navigation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-dashed border-border bg-muted/40 p-8 text-center text-sm text-muted-foreground">
            Documentation, workflow guides, and support resources will be available here.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
