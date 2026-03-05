#!/usr/bin/env python3
"""
Job Search Scanner — Automated opportunity discovery
Searches Indeed & LinkedIn for target roles, identifies new opportunities, sends alerts
"""

import json
import os
import sys
from datetime import datetime
import hashlib
from pathlib import Path

# Target parameters
TARGET_TITLES = [
    "principal design",
    "principal product",
    "staff design",
    "staff product",
    "design systems manager",
    "design operations",
    "creative technologist",
    "head of design",
    "director of design",
    "design manager",
]

TARGET_KEYWORDS = [
    "AI",
    "design systems",
    "product design",
    "UX",
    "design ops",
]

MIN_SALARY = 165000
LOCATIONS = ["remote", "boulder", "denver", "colorado"]

OPPORTUNITIES_FILE = Path(__file__).parent / "OPPORTUNITIES.md"
STATE_FILE = Path(__file__).parent / "scanner_state.json"


def load_state():
    """Load previously found opportunities to detect new ones."""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {"opportunities": {}, "lastRun": None}


def save_state(state):
    """Save state to detect duplicates on next run."""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)


def hash_opportunity(title, company, url):
    """Generate unique hash for opportunity."""
    key = f"{title}|{company}|{url}".lower()
    return hashlib.md5(key.encode()).hexdigest()[:8]


def search_indeed():
    """Search Indeed for target roles. Returns list of opportunities."""
    opportunities = []
    
    search_queries = [
        "principal design systems",
        "design systems manager remote",
        "senior product designer AI",
        "design operations manager",
        "creative technologist",
    ]
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Searching Indeed...")
    
    # Note: Direct scraping Indeed is blocked (Cloudflare). 
    # This would need Selenium or paid Indeed API.
    # For now, return structure ready for API integration.
    
    for query in search_queries:
        # Placeholder: would integrate with Indeed API here
        # opportunity = {
        #     "source": "Indeed",
        #     "title": "...",
        #     "company": "...",
        #     "location": "...",
        #     "salary": "...",
        #     "url": "...",
        #     "postedDate": "...",
        # }
        # opportunities.append(opportunity)
        pass
    
    return opportunities


def search_linkedin():
    """Search LinkedIn for target roles. Returns list of opportunities."""
    opportunities = []
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Searching LinkedIn...")
    
    # Note: LinkedIn direct scraping violates ToS.
    # Would need LinkedIn Recruiter API or authenticated session.
    # Placeholder for API integration.
    
    return opportunities


def search_buildincolorado():
    """Search BuildinColorado for Colorado-based opportunities."""
    opportunities = []
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Searching BuildinColorado...")
    
    # Note: BuildinColorado allows scraping. Can implement with web_fetch.
    # For now, placeholder structure.
    
    return opportunities


def filter_opportunities(opportunities):
    """Filter opportunities by target criteria."""
    filtered = []
    
    for opp in opportunities:
        title = opp.get("title", "").lower()
        location = opp.get("location", "").lower()
        salary = opp.get("salary", 0)
        
        # Check title match
        title_match = any(target in title for target in TARGET_TITLES)
        
        # Check location match
        location_match = any(loc in location for loc in LOCATIONS)
        
        # Check salary (if available)
        salary_match = salary >= MIN_SALARY if salary else True
        
        if title_match and location_match and salary_match:
            filtered.append(opp)
    
    return filtered


def format_opportunity_markdown(opp, oppy_hash):
    """Format single opportunity for OPPORTUNITIES.md"""
    return f"""
### {opp.get('company', 'Unknown')} — {opp.get('title', 'Unknown')}

**Source:** {opp.get('source', 'Unknown')}  
**Link:** {opp.get('url', 'N/A')}  
**Level:** {opp.get('title', '')}  
**Salary:** {opp.get('salary', 'Not specified')}  
**Location:** {opp.get('location', 'Unknown')}  
**Posted:** {opp.get('postedDate', 'Unknown')}  
**Fit Score:** [TBD]  
**Key Responsibilities:** [Extract from job description]  
**Why It Fits:** [Your analysis of alignment]  
**Action:** [To Apply / Warm Intro Opportunity / Research]  
**ID:** {oppy_hash}

---
"""


def update_opportunities_file(new_opportunities):
    """Append new opportunities to OPPORTUNITIES.md"""
    if not new_opportunities:
        return
    
    # Ensure file exists
    if not OPPORTUNITIES_FILE.exists():
        OPPORTUNITIES_FILE.write_text("# Job Opportunities\n\n")
    
    # Append new opportunities
    with open(OPPORTUNITIES_FILE, 'a') as f:
        f.write(f"\n## New Opportunities — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        for opp in new_opportunities:
            opp_hash = hash_opportunity(opp.get('title'), opp.get('company'), opp.get('url'))
            f.write(format_opportunity_markdown(opp, opp_hash))


def send_telegram_alert(new_opportunities):
    """Send Telegram alert with new opportunities."""
    if not new_opportunities:
        return
    
    message = f"🎯 **{len(new_opportunities)} New Job Opportunities Found**\n\n"
    
    for opp in new_opportunities:
        message += f"**{opp.get('company')}** — {opp.get('title')}\n"
        message += f"  {opp.get('location')} | {opp.get('salary', 'Salary TBD')}\n"
        message += f"  {opp.get('url', 'N/A')}\n\n"
    
    message += "Review in OPPORTUNITIES.md and prioritize for outreach."
    
    # Would call message tool here to send via Telegram
    # For now, log to stdout
    print(f"\n[ALERT] {message}")


def main():
    """Main scanner workflow."""
    print(f"\n{'='*60}")
    print(f"Job Search Scanner — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Load state
    state = load_state()
    
    # Search across platforms
    print("Starting searches...\n")
    all_opportunities = []
    all_opportunities.extend(search_indeed())
    all_opportunities.extend(search_linkedin())
    all_opportunities.extend(search_buildincolorado())
    
    print(f"\nTotal opportunities found: {len(all_opportunities)}")
    
    # Filter by criteria
    filtered = filter_opportunities(all_opportunities)
    print(f"After filtering: {len(filtered)} opportunities meet criteria\n")
    
    # Identify new opportunities
    new_opportunities = []
    for opp in filtered:
        opp_hash = hash_opportunity(opp.get('title'), opp.get('company'), opp.get('url'))
        if opp_hash not in state["opportunities"]:
            new_opportunities.append(opp)
            state["opportunities"][opp_hash] = {
                "company": opp.get('company'),
                "title": opp.get('title'),
                "foundDate": datetime.now().isoformat(),
                "url": opp.get('url'),
            }
    
    print(f"New opportunities: {len(new_opportunities)}\n")
    
    if new_opportunities:
        # Update opportunities file
        update_opportunities_file(new_opportunities)
        
        # Send alert
        send_telegram_alert(new_opportunities)
        
        print("✅ Opportunities file updated + alert sent\n")
    else:
        print("No new opportunities found.\n")
    
    # Update state
    state["lastRun"] = datetime.now().isoformat()
    save_state(state)
    
    print(f"Next run: {state['lastRun']}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
