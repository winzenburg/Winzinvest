#!/usr/bin/env python3
"""
Job Search Status Dashboard
Quick overview of the entire pipeline.
"""

import json
from pathlib import Path
from datetime import datetime

# Project paths
PROJECT_DIR = Path(__file__).parent.parent
DATA_DIR = PROJECT_DIR / "data"
RESEARCH_DIR = DATA_DIR / "research"
OUTREACH_DIR = DATA_DIR / "outreach"

COMPANIES_FILE = DATA_DIR / "companies.json"
CONTACTS_FILE = DATA_DIR / "contacts.json"


def load_json(filepath):
    """Load JSON file if exists."""
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    return []


def count_files_in_dir(directory):
    """Count JSON files in directory."""
    if not directory.exists():
        return 0
    return len(list(directory.glob("*.json")))


def main():
    """Display pipeline status."""
    print("\n" + "=" * 80)
    print("JOB SEARCH AUTOMATION - STATUS DASHBOARD")
    print("=" * 80)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Load data
    companies = load_json(COMPANIES_FILE)
    contacts = load_json(CONTACTS_FILE)
    
    # Count statuses
    researched_companies = len([c for c in companies if c.get('status') == 'researched'])
    
    pending_outreach = count_files_in_dir(OUTREACH_DIR / "pending")
    approved_outreach = count_files_in_dir(OUTREACH_DIR / "approved")
    rejected_outreach = count_files_in_dir(OUTREACH_DIR / "rejected")
    
    # Display stats
    print("\n📊 PIPELINE OVERVIEW")
    print("-" * 80)
    print(f"Companies discovered:     {len(companies)}")
    print(f"  └─ Researched:          {researched_companies}")
    print(f"\nDecision-makers identified: {len(contacts)}")
    print(f"\nOutreach messages:")
    print(f"  ⏳ Pending approval:    {pending_outreach}")
    print(f"  ✅ Approved:            {approved_outreach}")
    print(f"  ❌ Rejected:            {rejected_outreach}")
    
    # Top companies
    print("\n🎯 TARGET COMPANIES")
    print("-" * 80)
    for i, company in enumerate(companies[:10], 1):
        status = "✅" if company.get('status') == 'researched' else "⏳"
        print(f"{i:2}. {status} {company['name']:<20} ({company.get('designer_count_estimate', '?')} designers)")
    
    # Next actions
    print("\n📋 NEXT ACTIONS")
    print("-" * 80)
    if pending_outreach > 0:
        print(f"1. Review {pending_outreach} pending messages:")
        print(f"   python3 scripts/approval_queue.py")
    
    if approved_outreach > 0:
        print(f"2. Send {approved_outreach} approved messages via LinkedIn")
        print(f"   (Manual step - copy from: data/outreach/approved/)")
    
    if len(companies) < 50:
        print(f"3. Discover more companies:")
        print(f"   python3 scripts/discover_companies.py")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
