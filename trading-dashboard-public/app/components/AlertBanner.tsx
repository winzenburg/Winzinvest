'use client';

import { useEffect, useState } from 'react';
import { fetchWithAuth } from '@/lib/fetch-client';

interface Alert {
  id: string;
  severity: 'info' | 'warning' | 'critical';
  message: string;
  timestamp: string;
  category: string;
}

export default function AlertBanner() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());

  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        const res = await fetchWithAuth('/api/alerts');
        if (res.ok) {
          const data: unknown = await res.json();
          if (Array.isArray(data)) {
            // Validate each item has the minimum required fields
            const valid = data.filter(
              (item): item is Alert =>
                item !== null &&
                typeof item === 'object' &&
                typeof (item as Record<string, unknown>).id === 'string' &&
                typeof (item as Record<string, unknown>).message === 'string',
            );
            setAlerts(valid);
          }
        }
      } catch (error) {
        if (process.env.NODE_ENV === 'development') {
          console.error('Failed to fetch alerts:', error);
        }
      }
    };

    fetchAlerts();
    const interval = setInterval(fetchAlerts, 30000);
    return () => clearInterval(interval);
  }, []);

  const activeAlerts = alerts.filter(a => !dismissed.has(a.id));

  if (activeAlerts.length === 0) return null;

  return (
    <div className="mb-8 space-y-3">
      {activeAlerts.map(alert => (
        <div
          key={alert.id}
          className={`rounded-xl p-4 flex items-start justify-between ${
            alert.severity === 'critical'
              ? 'bg-red-50 border border-red-200'
              : alert.severity === 'warning'
              ? 'bg-orange-50 border border-orange-200'
              : 'bg-blue-50 border border-blue-200'
          }`}
        >
          <div className="flex items-start gap-3">
            <div className={`mt-0.5 ${
              alert.severity === 'critical'
                ? 'text-red-600'
                : alert.severity === 'warning'
                ? 'text-orange-600'
                : 'text-blue-600'
            }`}>
              {alert.severity === 'critical' ? '⚠️' : alert.severity === 'warning' ? '⚡' : 'ℹ️'}
            </div>
            <div>
              <div className={`font-semibold text-sm ${
                alert.severity === 'critical'
                  ? 'text-red-900'
                  : alert.severity === 'warning'
                  ? 'text-orange-900'
                  : 'text-blue-900'
              }`}>
                {alert.message}
              </div>
              <div className={`text-xs mt-1 ${
                alert.severity === 'critical'
                  ? 'text-red-700'
                  : alert.severity === 'warning'
                  ? 'text-orange-700'
                  : 'text-blue-700'
              }`}>
                {alert.category} • {new Date(alert.timestamp).toLocaleTimeString()}
              </div>
            </div>
          </div>
          <button
            type="button"
            aria-label="Dismiss alert"
            onClick={() => setDismissed(prev => new Set(prev).add(alert.id))}
            className={`text-lg font-bold ${
              alert.severity === 'critical'
                ? 'text-red-400 hover:text-red-600'
                : alert.severity === 'warning'
                ? 'text-orange-400 hover:text-orange-600'
                : 'text-blue-400 hover:text-blue-600'
            }`}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
