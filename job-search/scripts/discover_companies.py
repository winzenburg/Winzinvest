#!/usr/bin/env python3
"""
Company Discovery Engine
Finds target companies matching job search criteria.

Sources:
- Built In (startup database)
- LinkedIn (company search)
- Manual curated list
- Y Combinator batch lists

Output: data/companies.json
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import requests
from bs4 import BeautifulSoup

# Project paths
PROJECT_DIR = Path(__file__).parent.parent
DATA_DIR = PROJECT_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

COMPANIES_FILE = DATA_DIR / "companies.json"

# Target criteria
CRITERIA = {
    "min_designers": 15,
    "locations": ["Remote", "Colorado", "Denver", "Boulder", "USA"],
    "ai_keywords": [
        "AI", "artificial intelligence", "machine learning", "LLM",
        "generative AI", "AI-powered", "AI-native"
    ],
    "industries": [
        "SaaS", "Enterprise Software", "Developer Tools",
        "Design Tools", "Productivity", "Collaboration"
    ]
}


def load_companies() -> List[Dict]:
    """Load existing companies from JSON."""
    if COMPANIES_FILE.exists():
        with open(COMPANIES_FILE) as f:
            return json.load(f)
    return []


def save_companies(companies: List[Dict]):
    """Save companies to JSON."""
    with open(COMPANIES_FILE, 'w') as f:
        json.dump(companies, f, indent=2)
    print(f"✅ Saved {len(companies)} companies to {COMPANIES_FILE}")


def add_company(companies: List[Dict], company: Dict) -> List[Dict]:
    """Add company if not duplicate."""
    # Check for duplicates by name or URL
    existing_names = {c.get('name', '').lower() for c in companies}
    existing_urls = {c.get('url', '').lower() for c in companies}
    
    name_lower = company.get('name', '').lower()
    url_lower = company.get('url', '').lower()
    
    if name_lower in existing_names or url_lower in existing_urls:
        print(f"⏭️  Skipping duplicate: {company['name']}")
        return companies
    
    # Add UUID and timestamp
    company['id'] = str(uuid.uuid4())
    company['discovered_at'] = datetime.now().isoformat()
    company['status'] = 'discovered'
    
    companies.append(company)
    print(f"✅ Added: {company['name']}")
    return companies


def discover_built_in() -> List[Dict]:
    """
    Scrape Built In for companies.
    Note: This is a placeholder - actual scraping requires handling JS rendering.
    """
    print("\n🔍 Discovering companies from Built In...")
    
    # Placeholder - would need Playwright for JS-rendered pages
    # For now, return manual seed list
    return []


def discover_yc_companies() -> List[Dict]:
    """
    Find AI-focused companies from Y Combinator batches.
    """
    print("\n🔍 Discovering YC companies...")
    
    # YC company directory (public, no auth needed)
    # Placeholder - would scrape https://www.ycombinator.com/companies
    return []


def seed_manual_companies() -> List[Dict]:
    """
    Manual seed list of high-potential companies.
    These are known AI-forward, design-heavy companies.
    """
    print("\n🌱 Seeding manual company list...")
    
    seed_companies = [
        {
            "name": "Figma",
            "slug": "figma",
            "url": "https://figma.com",
            "linkedin": "https://linkedin.com/company/figma",
            "stage": "Public",
            "funding": "$332M+ (IPO pending)",
            "designer_count_estimate": 150,
            "location": "San Francisco, CA (Remote)",
            "ai_keywords": ["AI design tools", "auto-layout", "FigJam AI"],
            "why_target": "Leading design tool, heavy AI investment, large design team",
            "notes": "Check for Head of Design Ops or AI + Design roles"
        },
        {
            "name": "Notion",
            "slug": "notion",
            "url": "https://notion.so",
            "linkedin": "https://linkedin.com/company/notionhq",
            "stage": "Series C",
            "funding": "$343M",
            "designer_count_estimate": 50,
            "location": "San Francisco, CA (Remote)",
            "ai_keywords": ["Notion AI", "AI writing assistant", "generative AI"],
            "why_target": "AI-first product evolution, design-forward culture",
            "notes": "Recent AI features launch - good timing"
        },
        {
            "name": "Canva",
            "slug": "canva",
            "url": "https://canva.com",
            "linkedin": "https://linkedin.com/company/canva",
            "stage": "Series A (Unicorn)",
            "funding": "$572M",
            "designer_count_estimate": 200,
            "location": "Sydney, Australia (Remote)",
            "ai_keywords": ["Magic Write", "AI image generation", "AI design tools"],
            "why_target": "Massive design team, heavy AI integration, design ops need",
            "notes": "Large scale = need for ops infrastructure"
        },
        {
            "name": "Miro",
            "slug": "miro",
            "url": "https://miro.com",
            "linkedin": "https://linkedin.com/company/miro",
            "stage": "Series C",
            "funding": "$476M",
            "designer_count_estimate": 80,
            "location": "San Francisco, CA / Amsterdam (Remote)",
            "ai_keywords": ["Miro AI", "collaboration AI", "smart widgets"],
            "why_target": "Design collaboration tool, AI features, growing team",
            "notes": "Recently launched AI features - transformation phase"
        },
        {
            "name": "Webflow",
            "slug": "webflow",
            "url": "https://webflow.com",
            "linkedin": "https://linkedin.com/company/webflow-inc",
            "stage": "Series C",
            "funding": "$334M",
            "designer_count_estimate": 60,
            "location": "San Francisco, CA (Remote)",
            "ai_keywords": ["No-code", "visual development", "AI website generation"],
            "why_target": "Design-centric product, no-code + AI convergence",
            "notes": "Strong design culture, ops-mature"
        },
        {
            "name": "Framer",
            "slug": "framer",
            "url": "https://framer.com",
            "linkedin": "https://linkedin.com/company/framer",
            "stage": "Series B",
            "funding": "$50M",
            "designer_count_estimate": 40,
            "location": "Amsterdam (Remote)",
            "ai_keywords": ["AI prototyping", "design-to-code", "Framer AI"],
            "why_target": "Design tool for designers, AI-powered features",
            "notes": "Smaller but fast-growing, good timing"
        },
        {
            "name": "Linear",
            "slug": "linear",
            "url": "https://linear.app",
            "linkedin": "https://linkedin.com/company/linearapp",
            "stage": "Series B",
            "funding": "$52M",
            "designer_count_estimate": 25,
            "location": "San Francisco, CA (Remote)",
            "ai_keywords": ["Product management", "AI issue triage", "workflow automation"],
            "why_target": "Design-forward product tool, growing fast",
            "notes": "Exceptional design culture, could create role"
        },
        {
            "name": "Pitch",
            "slug": "pitch",
            "url": "https://pitch.com",
            "linkedin": "https://linkedin.com/company/pitch",
            "stage": "Series B",
            "funding": "$85M",
            "designer_count_estimate": 30,
            "location": "Berlin (Remote)",
            "ai_keywords": ["Presentation AI", "design suggestions", "AI templates"],
            "why_target": "Design-heavy product, AI features launching",
            "notes": "Strong design leadership, European remote-friendly"
        },
        {
            "name": "Airtable",
            "slug": "airtable",
            "url": "https://airtable.com",
            "linkedin": "https://linkedin.com/company/airtable",
            "stage": "Series F",
            "funding": "$1.36B",
            "designer_count_estimate": 70,
            "location": "San Francisco, CA (Remote)",
            "ai_keywords": ["AI-powered apps", "Airtable AI", "workflow automation"],
            "why_target": "Large design team, AI transformation underway",
            "notes": "Enterprise scale = design ops need"
        },
        {
            "name": "Superhuman",
            "slug": "superhuman",
            "url": "https://superhuman.com",
            "linkedin": "https://linkedin.com/company/superhuman",
            "stage": "Series C",
            "funding": "$108M",
            "designer_count_estimate": 20,
            "location": "San Francisco, CA (Remote)",
            "ai_keywords": ["AI email", "Superhuman AI", "inbox zero AI"],
            "why_target": "Design-obsessed culture, AI-first product",
            "notes": "Smaller team but exceptional design focus"
        }
    ]
    
    return seed_companies


def main():
    """Run discovery process."""
    print("=" * 60)
    print("COMPANY DISCOVERY ENGINE")
    print("=" * 60)
    
    # Load existing companies
    companies = load_companies()
    print(f"\n📊 Currently tracking: {len(companies)} companies")
    
    # Discover from sources
    discovered = []
    
    # Manual seed (immediate)
    manual = seed_manual_companies()
    discovered.extend(manual)
    
    # Built In (requires scraping)
    # built_in = discover_built_in()
    # discovered.extend(built_in)
    
    # YC companies (requires scraping)
    # yc = discover_yc_companies()
    # discovered.extend(yc)
    
    # Add new companies
    for company in discovered:
        companies = add_company(companies, company)
    
    # Save updated list
    save_companies(companies)
    
    print("\n" + "=" * 60)
    print(f"✅ Discovery complete: {len(companies)} total companies")
    print("=" * 60)


if __name__ == "__main__":
    main()
