// Page Template for Mission Control
// File: app/[page-name]/page.tsx

'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

// Import components
// import ComponentName from '../components/ComponentName';

interface PageData {
  // Define your data structure
  field: string;
  value: number;
}

/**
 * PageName - Brief description of what this page shows
 */
export default function PageName() {
  const [data, setData] = useState<PageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<string>('');

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await fetch('/api/endpoint');
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}: ${res.statusText}`);
        }
        const json = await res.json();
        
        // Type guard
        if (!isValidPageData(json)) {
          throw new Error('Invalid data format from API');
        }
        
        setData(json);
        setLastUpdate(new Date().toLocaleTimeString());
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
        console.error('Failed to fetch data:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
    
    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-stone-400">Loading...</div>
      </div>
    );
  }

  // Error state
  if (error || !data) {
    return (
      <div className="min-h-screen bg-stone-50 flex items-center justify-center">
        <div className="text-center">
          <div className="text-red-600 font-semibold mb-2">
            Error Loading Page
          </div>
          <div className="text-stone-500 text-sm">{error}</div>
          <div className="text-stone-400 text-xs mt-4">
            Check that the backend service is running
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-stone-50">
      <div className="max-w-7xl mx-auto px-8 py-12">
        
        {/* Header */}
        <header className="mb-16 pb-8 border-b border-stone-200">
          <div className="flex justify-between items-start mb-6">
            <h1 className="font-serif text-5xl font-bold text-slate-900 tracking-tight">
              Page Title
            </h1>
            
            {/* Status indicator */}
            <div className="text-right">
              <div className="flex items-center gap-2 text-sm text-stone-500">
                <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                <span>Live</span>
              </div>
              <div className="text-xs text-stone-400 mt-1">
                Updated {lastUpdate}
              </div>
            </div>
          </div>
          
          {/* Navigation */}
          <nav className="flex gap-4">
            <Link
              href="/"
              className="px-4 py-2 bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg text-sm font-semibold transition-colors"
            >
              ← Dashboard
            </Link>
            <Link
              href="/institutional"
              className="px-4 py-2 bg-stone-100 hover:bg-stone-200 text-stone-700 rounded-lg text-sm font-semibold transition-colors"
            >
              Institutional View
            </Link>
          </nav>
        </header>

        {/* Main Content */}
        <main>
          {/* Key Metrics Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
            <MetricCard
              label="Metric 1"
              value={formatValue(data.value)}
              color="text-sky-600"
            />
            {/* Add more metric cards */}
          </div>

          {/* Content Section */}
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-12">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
              Section Title
            </h2>
            
            {/* Section content */}
            <div className="text-stone-600 leading-relaxed">
              {data.field}
            </div>
          </div>

          {/* Data Table */}
          <div className="bg-white border border-stone-200 rounded-xl p-8">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-6">
              Data Table
            </h2>
            
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="border-b border-stone-200">
                  <tr>
                    <th className="text-left py-3 px-2 font-semibold text-stone-600">
                      Column 1
                    </th>
                    <th className="text-right py-3 px-2 font-semibold text-stone-600">
                      Column 2
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="border-b border-stone-100 hover:bg-stone-50">
                    <td className="py-3 px-2 text-stone-900">Data</td>
                    <td className="py-3 px-2 text-right text-stone-900">Value</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </main>

        {/* Footer */}
        <footer className="mt-16 pt-8 border-t border-stone-200 text-center text-sm text-stone-400">
          <p>Mission Control Trading System</p>
          <p className="mt-2">
            Past performance does not guarantee future results. Trading involves risk of loss.
          </p>
        </footer>
      </div>
    </div>
  );
}

// Helper Components

function MetricCard({ 
  label, 
  value, 
  color 
}: { 
  label: string; 
  value: string; 
  color: string;
}) {
  return (
    <div className="bg-white border border-stone-200 rounded-xl p-6 hover:shadow-lg transition-shadow">
      <div className="text-xs font-semibold uppercase tracking-wider text-stone-500 mb-2">
        {label}
      </div>
      <div className={`font-serif text-4xl font-bold ${color}`}>
        {value}
      </div>
    </div>
  );
}

// Type Guards

function isValidPageData(data: unknown): data is PageData {
  return (
    typeof data === 'object' &&
    data !== null &&
    'field' in data &&
    'value' in data &&
    typeof (data as PageData).field === 'string' &&
    typeof (data as PageData).value === 'number'
  );
}

// Utility Functions

function formatValue(value: number): string {
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

// Quality Gates Checklist:
// [ ] Type guards for all external data
// [ ] Error handling with try-catch
// [ ] Loading state shown
// [ ] Error state shown with helpful message
// [ ] No console.log (console.error in catch is OK)
// [ ] Responsive design (mobile/tablet/desktop)
// [ ] WCAG AA contrast (4.5:1 for text)
// [ ] Semantic HTML (header, nav, main, footer)
// [ ] Keyboard navigation works
// [ ] Data timestamps visible
// [ ] Auto-refresh every 30s
