import React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../components/ui/Card';
import { Settings } from 'lucide-react';

export function SettingsPage() {
  return (
    <div className="space-y-6 max-w-5xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold text-navy tracking-tight">Settings</h2>
        <p className="text-sm text-muted-foreground mt-1">
          System parameters and workspace preferences.
        </p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Settings className="h-5 w-5 text-primary" />
            <CardTitle>Application Settings Shell</CardTitle>
          </div>
          <CardDescription>
            Placeholder destination for support navigation.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="rounded-lg border border-dashed border-border bg-muted/40 p-8 text-center text-sm text-muted-foreground">
            Settings controls will be implemented in subsequent phases.
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
