#!/usr/bin/env python3
"""
Research Agent
Deep-dive research on discovered companies.

For each company:
1. Generate company brief (stage, product, design team insights)
2. Identify decision-makers (LinkedIn scraping or manual research)
3. Find personalization hooks (recent news, launches, hiring)
4. Create outreach angles

Output: data/research/[company_slug].json
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("ℹ️  anthropic module not available, using mock research mode")

# Project paths
PROJECT_DIR = Path(__file__).parent.parent
DATA_DIR = PROJECT_DIR / "data"
RESEARCH_DIR = DATA_DIR / "research"
RESEARCH_DIR.mkdir(exist_ok=True)

COMPANIES_FILE = DATA_DIR / "companies.json"
CONTACTS_FILE = DATA_DIR / "contacts.json"

# Load API key
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("⚠️  ANTHROPIC_API_KEY not set. Using mock research mode.")


def load_companies() -> List[Dict]:
    """Load companies from JSON."""
    with open(COMPANIES_FILE) as f:
        return json.load(f)


def load_contacts() -> List[Dict]:
    """Load existing contacts from JSON."""
    if CONTACTS_FILE.exists():
        with open(CONTACTS_FILE) as f:
            return json.load(f)
    return []


def save_contacts(contacts: List[Dict]):
    """Save contacts to JSON."""
    with open(CONTACTS_FILE, 'w') as f:
        json.dump(contacts, f, indent=2)
    print(f"✅ Saved {len(contacts)} contacts")


def generate_company_brief(company: Dict) -> Dict:
    """
    Generate AI-powered company research brief.
    Uses Claude to create strategic insights for outreach.
    """
    prompt = f"""You are a job search strategist helping someone target companies for an "AI-Augmented Design Operations Leader" role.

Company: {company['name']}
Stage: {company.get('stage', 'Unknown')}
Product: {company.get('url', '')}
Designer Count: {company.get('designer_count_estimate', 'Unknown')}
AI Keywords: {', '.join(company.get('ai_keywords', []))}

Generate a strategic company brief in JSON format:

{{
  "executive_summary": "2-sentence overview of why this company is a good target",
  "design_ops_need": "Why they need a Design Ops leader (scale, complexity, AI integration)",
  "ai_transformation_stage": "Where they are in AI adoption (early/mid/mature)",
  "pain_points": ["List 3-4 likely pain points their design team faces"],
  "opportunity_angles": ["List 2-3 specific ways Ryan can add value"],
  "personalization_hooks": ["List 2-3 recent company news/launches to reference"],
  "outreach_strategy": "Recommended approach (direct to VP Design, via mutual connection, etc.)",
  "decision_makers_likely_titles": ["VP of Design", "Head of Design", "CPO"]
}}

Be specific and strategic. Focus on what makes THIS company ready for this role."""

    if not ANTHROPIC_AVAILABLE or not ANTHROPIC_API_KEY:
        # Mock research for testing
        return {
            "executive_summary": f"{company['name']} is a design-forward company with AI features and a growing design team.",
            "design_ops_need": "Growing team needs systematic operations and AI integration.",
            "ai_transformation_stage": "mid",
            "pain_points": [
                "Scaling design output without proportional headcount growth",
                "Inconsistent AI tool adoption across design team",
                "Need for systematic design-to-development handoff"
            ],
            "opportunity_angles": [
                "Architect AI-augmented design workflows",
                "Build design ops infrastructure for 2x team growth"
            ],
            "personalization_hooks": [
                f"Recent AI features launch",
                f"Growing design team"
            ],
            "outreach_strategy": "Direct LinkedIn outreach to VP of Design",
            "decision_makers_likely_titles": ["VP of Design", "Head of Design", "Director of Design"]
        }
    
    # Use Claude for real research
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )
    
    # Parse JSON response
    try:
        return json.loads(message.content[0].text)
    except json.JSONDecodeError:
        # Fallback if JSON parsing fails
        return {"raw_response": message.content[0].text}


def identify_decision_makers(company: Dict, brief: Dict) -> List[Dict]:
    """
    Identify likely decision-makers at the company.
    
    In a full implementation, this would:
    1. Scrape LinkedIn for employees with target titles
    2. Use Hunter.io/RocketReach for email addresses
    3. Find mutual connections
    
    For now, returns placeholder contacts with manual research notes.
    """
    likely_titles = brief.get('decision_makers_likely_titles', [
        "VP of Design",
        "Head of Design",
        "Director of Design",
        "Chief Design Officer",
        "Head of Design Operations"
    ])
    
    # Placeholder contacts (manual research needed)
    contacts = []
    for title in likely_titles[:2]:  # Top 2 most likely
        contact = {
            "company_id": company['id'],
            "company_name": company['name'],
            "name": f"[Research Needed] - {title}",
            "title": title,
            "linkedin": f"{company.get('linkedin', '')}/people",
            "email": None,
            "status": "needs_research",
            "research_notes": f"Find current {title} at {company['name']} via LinkedIn",
            "outreach_priority": "high" if "VP" in title or "Head" in title else "medium"
        }
        contacts.append(contact)
    
    return contacts


def research_company(company: Dict) -> Dict:
    """
    Full research cycle for one company.
    Returns research brief + identified contacts.
    """
    print(f"\n🔍 Researching: {company['name']}")
    
    # Generate AI brief
    brief = generate_company_brief(company)
    
    # Identify decision-makers
    contacts = identify_decision_makers(company, brief)
    
    # Save research brief
    research_file = RESEARCH_DIR / f"{company['slug']}.json"
    research_data = {
        "company": company,
        "brief": brief,
        "contacts": contacts,
        "researched_at": datetime.now().isoformat(),
        "status": "complete"
    }
    
    with open(research_file, 'w') as f:
        json.dump(research_data, f, indent=2)
    
    print(f"✅ Research saved: {research_file.name}")
    print(f"   Decision-makers identified: {len(contacts)}")
    
    return research_data


def main():
    """Research all discovered companies that need research."""
    print("=" * 60)
    print("RESEARCH AGENT")
    print("=" * 60)
    
    # Load companies
    companies = load_companies()
    print(f"\n📊 Total companies: {len(companies)}")
    
    # Filter companies needing research
    needs_research = [
        c for c in companies 
        if c.get('status') in ['discovered', 'needs_research']
    ]
    
    if not needs_research:
        print("✅ All companies already researched!")
        return
    
    print(f"🔬 Companies needing research: {len(needs_research)}")
    
    # Research each company
    all_contacts = load_contacts()
    
    for company in needs_research:
        try:
            research = research_company(company)
            
            # Add contacts to global list
            for contact in research['contacts']:
                # Add UUID if not present
                if 'id' not in contact:
                    import uuid
                    contact['id'] = str(uuid.uuid4())
                all_contacts.append(contact)
            
            # Update company status
            company['status'] = 'researched'
            
        except Exception as e:
            print(f"❌ Error researching {company['name']}: {e}")
            company['status'] = 'research_failed'
    
    # Save updated companies
    with open(COMPANIES_FILE, 'w') as f:
        json.dump(companies, f, indent=2)
    
    # Save contacts
    save_contacts(all_contacts)
    
    print("\n" + "=" * 60)
    print(f"✅ Research complete!")
    print(f"   Companies researched: {len(needs_research)}")
    print(f"   Total contacts: {len(all_contacts)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
