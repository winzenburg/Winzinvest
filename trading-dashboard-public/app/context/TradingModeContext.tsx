'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { fetchWithAuth } from '@/lib/fetch-client';

type ViewMode = 'paper' | 'live';

interface ModeStatus {
  available: boolean;
  lastUpdate: string | null;
  allocationPct: number | null;
}

interface TradingModeState {
  /** Which tab the user is currently viewing */
  viewMode: ViewMode;
  /** Which mode the backend is actually executing trades in */
  activeMode: ViewMode | null;
  /** Whether the paper IB Gateway (port 4002) is reachable right now */
  paperGatewayUp: boolean;
  /** Availability info for each mode (snapshot exists + freshness) */
  modes: Record<ViewMode, ModeStatus>;
  /** Switch the viewed tab (display only — does not change execution) */
  setViewMode: (mode: ViewMode) => void;
  /**
   * Switch the active execution mode.
   * Calls POST /api/trading-modes, updates trading/.env and active_mode.json.
   * Returns true on success, false on failure.
   */
  activateMode: (mode: ViewMode) => Promise<boolean>;
  /** True while the initial /api/trading-modes call is in flight */
  loading: boolean;
  /** Non-null when activateMode() is in flight */
  activating: ViewMode | null;
}

const DEFAULT_MODES: Record<ViewMode, ModeStatus> = {
  paper: { available: false, lastUpdate: null, allocationPct: null },
  live: { available: false, lastUpdate: null, allocationPct: null },
};

const TradingModeContext = createContext<TradingModeState>({
  viewMode: 'paper',
  activeMode: null,
  paperGatewayUp: false,
  modes: DEFAULT_MODES,
  setViewMode: () => {},
  activateMode: async () => false,
  loading: true,
  activating: null,
});

export function TradingModeProvider({ children }: { children: ReactNode }) {
  const [viewMode, setViewModeRaw] = useState<ViewMode>('paper');
  const [activeMode, setActiveMode] = useState<ViewMode | null>(null);
  const [paperGatewayUp, setPaperGatewayUp] = useState(false);
  const [modes, setModes] = useState<Record<ViewMode, ModeStatus>>(DEFAULT_MODES);
  const [loading, setLoading] = useState(true);
  const [activating, setActivating] = useState<ViewMode | null>(null);

  const setViewMode = useCallback((mode: ViewMode) => {
    setViewModeRaw(mode);
    try {
      localStorage.setItem('mc_view_mode', mode);
    } catch { /* SSR / incognito */ }
  }, []);

  // Restore saved view preference on mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem('mc_view_mode');
      if (stored === 'paper' || stored === 'live') {
        setViewModeRaw(stored);
      }
    } catch { /* SSR / incognito */ }
  }, []);

  const fetchModes = useCallback(async () => {
    try {
      const res = await fetchWithAuth('/api/trading-modes');
      if (!res.ok) return;
      const json = await res.json();

      const active = json.activeMode === 'live' ? 'live'
        : json.activeMode === 'paper' ? 'paper'
        : null;
      setActiveMode(active);
      setPaperGatewayUp(json.paperGatewayUp === true);

      const paper: ModeStatus = {
        available: json.modes?.paper?.available ?? false,
        lastUpdate: json.modes?.paper?.lastUpdate ?? null,
        allocationPct: json.modes?.paper?.allocationPct ?? null,
      };
      const live: ModeStatus = {
        available: json.modes?.live?.available ?? false,
        lastUpdate: json.modes?.live?.lastUpdate ?? null,
        allocationPct: json.modes?.live?.allocationPct ?? null,
      };
      setModes({ paper, live });

      // Auto-select active mode as view if user hasn't set a preference yet
      if (active) {
        try {
          if (!localStorage.getItem('mc_view_mode')) setViewModeRaw(active);
        } catch { /* SSR */ }
      }
    } catch { /* network error — keep defaults */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchModes();
    const interval = setInterval(fetchModes, 30_000);
    return () => clearInterval(interval);
  }, [fetchModes]);

  /** POST /api/trading-modes — switches backend execution mode */
  const activateMode = useCallback(async (mode: ViewMode): Promise<boolean> => {
    setActivating(mode);
    try {
      const res = await fetchWithAuth('/api/trading-modes', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode }),
      });
      if (!res.ok) return false;
      const json = await res.json();
      if (json.ok) {
        setActiveMode(mode);
        // Also switch view to match newly activated mode
        setViewMode(mode);
        // Refresh mode availability after switch
        await fetchModes();
        return true;
      }
      return false;
    } catch {
      return false;
    } finally {
      setActivating(null);
    }
  }, [fetchModes, setViewMode]);

  return (
    <TradingModeContext.Provider
      value={{ viewMode, activeMode, paperGatewayUp, modes, setViewMode, activateMode, loading, activating }}
    >
      {children}
    </TradingModeContext.Provider>
  );
}

export function useTradingMode() {
  return useContext(TradingModeContext);
}
