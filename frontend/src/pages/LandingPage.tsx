import React from 'react';
import { Link } from 'react-router-dom';
import { Shield, ArrowRight } from 'lucide-react';
import { Button } from '../components/ui/Button';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';

export function LandingPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md text-center p-6 shadow-modal">
        <CardHeader className="items-center pb-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-surface-subtle text-primary border border-primary/20 mb-2">
            <Shield className="h-6 w-6" />
          </div>
          <CardTitle className="text-2xl font-bold text-navy">Policy Explainer</CardTitle>
          <CardDescription className="text-sm font-medium text-primary">
            Frontend foundation initialized
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4 pt-4">
          <p className="text-sm text-muted-foreground leading-relaxed">
            Enterprise insurance intelligence shell is active. System ready for module development.
          </p>
          <div className="pt-2 flex flex-col gap-2">
            <Link to="/app/explainer" className="w-full">
              <Button className="w-full gap-2">
                Open Policy Explainer Workspace <ArrowRight className="h-4 w-4" />
              </Button>
            </Link>
            <Link to="/login" className="w-full">
              <Button variant="outline" className="w-full">
                Sign In to Workspace
              </Button>
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
