'use client';

import { useState, useEffect } from 'react';
import { format } from 'date-fns';

type WaitlistEntry = {
  id: string;
  email: string;
  tier: string;
  status: string;
  source: string;
  metadata: Record<string, unknown> | null;
  invitedAt: string | null;
  createdAt: string;
  updatedAt: string;
};

type Stats = {
  total: number;
  pending: number;
  invited: number;
  active: number;
  rejected: number;
  byTier: {
    intelligence: number;
    automation: number;
    professional: number;
    founding: number;
  };
};

export default function WaitlistAdmin() {
  const [entries, setEntries] = useState<WaitlistEntry[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [tierFilter, setTierFilter] = useState<string>('all');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});

  useEffect(() => {
    fetchWaitlist();
  }, [statusFilter, tierFilter]);

  async function fetchWaitlist() {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (statusFilter !== 'all') params.set('status', statusFilter);
      if (tierFilter !== 'all') params.set('tier', tierFilter);

      const res = await fetch(`/api/admin/waitlist?${params}`);
      if (res.ok) {
        const data = await res.json();
        setEntries(data.entries || []);
        setStats(data.stats || null);
      }
    } catch (error) {
      console.error('Failed to fetch waitlist:', error);
    } finally {
      setLoading(false);
    }
  }

  async function updateEntry(id: string, status: string, note?: string) {
    setActionLoading(id);
    try {
      const metadata = note ? { note } : undefined;
      const res = await fetch('/api/admin/waitlist', {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, status, metadata }),
      });

      if (res.ok) {
        await fetchWaitlist();
      }
    } catch (error) {
      console.error('Failed to update entry:', error);
    } finally {
      setActionLoading(null);
      setNotes((prev) => {
        const updated = { ...prev };
        delete updated[id];
        return updated;
      });
    }
  }

  async function sendInvitation(id: string) {
    setActionLoading(id);
    try {
      const res = await fetch('/api/admin/send-invitation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ waitlistId: id }),
      });

      if (res.ok) {
        await fetchWaitlist();
      }
    } catch (error) {
      console.error('Failed to send invitation:', error);
    } finally {
      setActionLoading(null);
    }
  }

  function exportCSV() {
    const headers = ['Email', 'Tier', 'Status', 'Source', 'Created At', 'Invited At'];
    const rows = entries.map((e) => [
      e.email,
      e.tier,
      e.status,
      e.source,
      format(new Date(e.createdAt), 'yyyy-MM-dd HH:mm'),
      e.invitedAt ? format(new Date(e.invitedAt), 'yyyy-MM-dd HH:mm') : '',
    ]);

    const csv = [headers, ...rows].map((row) => row.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `waitlist-${format(new Date(), 'yyyy-MM-dd')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const tierBadgeColor = {
    intelligence: 'bg-blue-100 text-blue-800',
    automation: 'bg-purple-100 text-purple-800',
    professional: 'bg-amber-100 text-amber-800',
    founding: 'bg-rose-100 text-rose-800',
  };

  const statusBadgeColor = {
    pending: 'bg-gray-100 text-gray-800',
    invited: 'bg-blue-100 text-blue-800',
    active: 'bg-green-100 text-green-800',
    rejected: 'bg-red-100 text-red-800',
  };

  return (
    <div className="min-h-screen bg-gray-50 py-8 px-4">
      <div className="max-w-7xl mx-auto">
        <div className="mb-8">
          <h1 className="text-3xl font-bold text-gray-900 mb-2">Waitlist Manager</h1>
          <p className="text-gray-600">Manage beta testing signups and send invitations</p>
        </div>

        {stats && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-600">Total Signups</div>
              <div className="text-2xl font-bold">{stats.total}</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-600">Pending</div>
              <div className="text-2xl font-bold">{stats.pending}</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-600">Invited</div>
              <div className="text-2xl font-bold">{stats.invited}</div>
            </div>
            <div className="bg-white p-4 rounded-lg shadow">
              <div className="text-sm text-gray-600">Active</div>
              <div className="text-2xl font-bold text-green-600">{stats.active}</div>
            </div>
          </div>
        )}

        <div className="bg-white rounded-lg shadow mb-6 p-4">
          <div className="flex flex-wrap gap-4 items-center">
            <div>
              <label className="text-sm text-gray-600 mr-2">Status:</label>
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="border border-gray-300 rounded px-3 py-1.5"
              >
                <option value="all">All</option>
                <option value="pending">Pending</option>
                <option value="invited">Invited</option>
                <option value="active">Active</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>

            <div>
              <label className="text-sm text-gray-600 mr-2">Tier:</label>
              <select
                value={tierFilter}
                onChange={(e) => setTierFilter(e.target.value)}
                className="border border-gray-300 rounded px-3 py-1.5"
              >
                <option value="all">All</option>
                <option value="intelligence">Intelligence</option>
                <option value="automation">Automation</option>
                <option value="professional">Professional</option>
                <option value="founding">Founding</option>
              </select>
            </div>

            <button
              onClick={exportCSV}
              className="ml-auto px-4 py-1.5 bg-gray-600 text-white rounded hover:bg-gray-700"
            >
              Export CSV
            </button>
          </div>
        </div>

        {loading ? (
          <div className="text-center py-12 text-gray-500">Loading...</div>
        ) : (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full">
              <thead className="bg-gray-50 border-b">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Email</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Tier</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Status</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Signed Up</th>
                  <th className="px-4 py-3 text-left text-sm font-semibold text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr key={entry.id} className="border-b hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-900">{entry.email}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block px-2 py-1 text-xs font-medium rounded ${
                          tierBadgeColor[entry.tier as keyof typeof tierBadgeColor] ||
                          'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {entry.tier}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block px-2 py-1 text-xs font-medium rounded ${
                          statusBadgeColor[entry.status as keyof typeof statusBadgeColor] ||
                          'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {entry.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">
                      {format(new Date(entry.createdAt), 'MMM dd, yyyy')}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        {entry.status === 'pending' && (
                          <>
                            <button
                              onClick={() => sendInvitation(entry.id)}
                              disabled={actionLoading === entry.id}
                              className="px-3 py-1 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                            >
                              {actionLoading === entry.id ? 'Sending...' : 'Send Invite'}
                            </button>
                            <button
                              onClick={() => updateEntry(entry.id, 'rejected')}
                              disabled={actionLoading === entry.id}
                              className="px-3 py-1 text-xs bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50"
                            >
                              Reject
                            </button>
                          </>
                        )}
                        {entry.status === 'invited' && (
                          <button
                            onClick={() => updateEntry(entry.id, 'active')}
                            disabled={actionLoading === entry.id}
                            className="px-3 py-1 text-xs bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
                          >
                            Mark Active
                          </button>
                        )}
                        <input
                          type="text"
                          placeholder="Add note..."
                          value={notes[entry.id] || ''}
                          onChange={(e) =>
                            setNotes((prev) => ({ ...prev, [entry.id]: e.target.value }))
                          }
                          className="px-2 py-1 text-xs border border-gray-300 rounded w-32"
                        />
                        <button
                          onClick={() => updateEntry(entry.id, entry.status, notes[entry.id])}
                          disabled={!notes[entry.id] || actionLoading === entry.id}
                          className="px-3 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-700 disabled:opacity-50"
                        >
                          Save Note
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {entries.length === 0 && (
              <div className="text-center py-12 text-gray-500">No entries found</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
