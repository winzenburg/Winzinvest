#!/usr/bin/env python3
"""
Outreach Generator
Creates personalized outreach messages for each contact.

Uses:
- Company research briefs
- LinkedIn message templates
- Contact information

Output: data/outreach/pending/[contact_id].json
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List

# Project paths
PROJECT_DIR = Path(__file__).parent.parent
DATA_DIR = PROJECT_DIR / "data"
RESEARCH_DIR = DATA_DIR / "research"
OUTREACH_DIR = DATA_DIR / "outreach"
PENDING_DIR = OUTREACH_DIR / "pending"
TEMPLATES_DIR = PROJECT_DIR / "templates"

# Create directories
PENDING_DIR.mkdir(parents=True, exist_ok=True)

CONTACTS_FILE = DATA_DIR / "contacts.json"
LINKEDIN_TEMPLATE = TEMPLATES_DIR / "linkedin_cold.txt"


def load_contacts() -> List[Dict]:
    """Load contacts from JSON."""
    with open(CONTACTS_FILE) as f:
        return json.load(f)


def load_research(company_slug: str) -> Dict:
    """Load research brief for a company."""
    research_file = RESEARCH_DIR / f"{company_slug}.json"
    if research_file.exists():
        with open(research_file) as f:
            return json.load(f)
    return {}


def load_template(template_name: str = "linkedin_cold") -> str:
    """Load message template."""
    template_file = TEMPLATES_DIR / f"{template_name}.txt"
    with open(template_file) as f:
        return f.read()


def generate_personalization_hook(company: Dict, brief: Dict) -> str:
    """
    Generate a specific, timely hook for the message.
    Uses company research to find something recent/specific to mention.
    """
    hooks = brief.get('personalization_hooks', [])
    
    if hooks:
        # Use first hook from research
        return hooks[0]
    
    # Fallback to generic but still specific
    ai_keywords = company.get('ai_keywords', [])
    if ai_keywords:
        return f"integrating AI into your product ({', '.join(ai_keywords[:2])})"
    
    return "growing your design team and capabilities"


def generate_opportunity_angle(brief: Dict) -> str:
    """
    Create a specific value proposition for this company.
    Based on research, what can Ryan uniquely offer?
    """
    angles = brief.get('opportunity_angles', [])
    
    if angles:
        # Pick strongest angle
        return angles[0] + "."
    
    # Fallback
    return "I've built frameworks that help design teams adopt AI systematically—not just adding tools, but transforming how they work."


def estimate_team_size(company: Dict) -> str:
    """Estimate current design team size."""
    count = company.get('designer_count_estimate', 20)
    
    if count >= 100:
        return "100+"
    elif count >= 50:
        return "50+"
    elif count >= 20:
        return "20+"
    else:
        return "15+"


def calculate_multiplier(team_size: str) -> str:
    """Calculate output multiplier claim based on team size."""
    # Conservative: claim 2-3x output improvement
    return "3"


def generate_message(contact: Dict, company: Dict, brief: Dict) -> Dict:
    """
    Generate personalized outreach message for one contact.
    """
    # Load template
    template = load_template("linkedin_cold")
    
    # Get contact name (or placeholder)
    name = contact.get('name', 'there')
    if name.startswith("[Research Needed]"):
        name = contact.get('title', 'there')  # Use title if name not found
    
    # Generate dynamic content
    personalization_hook = generate_personalization_hook(company, brief)
    opportunity_angle = generate_opportunity_angle(brief)
    team_size = estimate_team_size(company)
    multiplier = calculate_multiplier(team_size)
    
    # Fill template
    message = template.format(
        company_name=company['name'],
        name=name,
        personalization_hook=personalization_hook,
        team_size=team_size,
        multiplier=multiplier,
        opportunity_angle=opportunity_angle,
        company_slug=company['slug']
    )
    
    # Create outreach record
    outreach = {
        "id": str(uuid.uuid4()),
        "contact_id": contact['id'],
        "company_id": company['id'],
        "contact_name": contact['name'],
        "contact_title": contact['title'],
        "company_name": company['name'],
        "channel": "linkedin",
        "message": message,
        "template_used": "linkedin_cold",
        "personalization": {
            "hook": personalization_hook,
            "angle": opportunity_angle,
            "team_size": team_size,
            "multiplier": multiplier
        },
        "status": "pending_approval",
        "generated_at": datetime.now().isoformat(),
        "utm_params": {
            "utm_source": "linkedin",
            "utm_campaign": "outreach",
            "utm_medium": company['slug']
        }
    }
    
    return outreach


def save_outreach(outreach: Dict):
    """Save outreach message to pending queue."""
    filename = f"{outreach['id']}.json"
    filepath = PENDING_DIR / filename
    
    with open(filepath, 'w') as f:
        json.dump(outreach, f, indent=2)
    
    return filepath


def main():
    """Generate outreach for all contacts needing messages."""
    print("=" * 60)
    print("OUTREACH GENERATOR")
    print("=" * 60)
    
    # Load contacts
    contacts = load_contacts()
    print(f"\n📊 Total contacts: {len(contacts)}")
    
    # Filter contacts needing outreach
    needs_outreach = [
        c for c in contacts
        if c.get('status') in ['needs_research', 'researched', None]
    ]
    
    if not needs_outreach:
        print("✅ All contacts already have outreach generated!")
        return
    
    print(f"✉️  Contacts needing outreach: {len(needs_outreach)}")
    
    # Generate outreach for each contact
    generated = 0
    
    for contact in needs_outreach:
        try:
            # Find company
            company_name = contact.get('company_name', '')
            company_slug = company_name.lower().replace(' ', '-') if company_name else None
            
            if not company_slug:
                print(f"⏭️  Skipping {contact.get('name', 'unknown')}: no company info")
                continue
            
            # Load research
            research = load_research(company_slug)
            if not research:
                print(f"⏭️  Skipping {contact.get('name', 'unknown')}: no research found")
                continue
            
            company = research.get('company', {})
            brief = research.get('brief', {})
            
            # Generate message
            outreach = generate_message(contact, company, brief)
            
            # Save to pending queue
            filepath = save_outreach(outreach)
            
            print(f"✅ Generated: {contact['company_name']} - {contact['title']}")
            print(f"   Saved to: {filepath.name}")
            
            generated += 1
            
        except Exception as e:
            print(f"❌ Error generating for {contact.get('name', 'unknown')}: {e}")
    
    print("\n" + "=" * 60)
    print(f"✅ Outreach generation complete!")
    print(f"   Messages generated: {generated}")
    print(f"   Pending approval: {len(list(PENDING_DIR.glob('*.json')))}")
    print("=" * 60)
    print(f"\n📋 Next: Review messages with: python3 scripts/approval_queue.py")


if __name__ == "__main__":
    main()
