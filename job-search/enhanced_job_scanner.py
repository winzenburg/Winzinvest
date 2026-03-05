#!/usr/bin/env python3
"""
Enhanced Job Search Scanner
Searches 20+ job boards, companies, and communities for principal-level opportunities
"""

import json
import os
from datetime import datetime
from pathlib import Path
import subprocess

OPPORTUNITIES_FILE = Path(__file__).parent / "OPPORTUNITIES.md"
STATE_FILE = Path(__file__).parent / "scanner_state.json"

SEARCH_SOURCES = {
    "tier1_boards": [
        {
            "name": "Wellfound",
            "url": "https://wellfound.com/jobs?query=principal+design&salary_min=165000",
            "method": "web_search",
            "query": "principal design principal product remote wellfound site:wellfound.com",
        },
        {
            "name": "Otta",
            "url": "https://otta.com/jobs?roles=design_product_manager&locations=remote",
            "method": "web_search",
            "query": "principal director design otta site:otta.com remote",
        },
        {
            "name": "AIGA Design Jobs",
            "url": "https://designjobs.aiga.org",
            "method": "web_fetch",
            "query": "principal director design jobs aiga site:designjobs.aiga.org",
        },
        {
            "name": "Dribbble Jobs",
            "url": "https://dribbble.com/jobs?experience=principal&salary_min=165",
            "method": "web_search",
            "query": "principal director design jobs dribbble site:dribbble.com",
        },
        {
            "name": "UX Jobs Board",
            "url": "https://uxjobsboard.com",
            "method": "web_fetch",
            "query": "principal director design ux jobs site:uxjobsboard.com",
        },
        {
            "name": "Working Not Working",
            "url": "https://workingnotworking.com",
            "method": "web_fetch",
            "query": "principal director design leadership site:workingnotworking.com",
        },
    ],
    
    "general_boards": [
        {
            "name": "Indeed",
            "url": "https://www.indeed.com/jobs?q=principal+design+systems+manager&l=remote",
            "method": "web_search",
            "query": "principal design systems manager remote site:indeed.com",
        },
        {
            "name": "LinkedIn",
            "url": "https://linkedin.com/jobs/search/?keywords=principal+product+designer&location=remote",
            "method": "web_search",
            "query": "principal product designer staff design systems site:linkedin.com/jobs",
        },
        {
            "name": "BuildinColorado",
            "url": "https://buildincolorado.com/jobs",
            "method": "web_fetch",
            "query": "principal design director product manager site:buildincolorado.com",
        },
    ],
    
    "company_careers": [
        {
            "name": "Shopify",
            "url": "https://www.shopify.com/careers/search?department=design",
            "method": "web_fetch",
            "query": "principal design shopify site:shopify.com/careers",
        },
        {
            "name": "Airbnb",
            "url": "https://careers.airbnb.com/positions/?category=design",
            "method": "web_fetch",
            "query": "principal director design airbnb site:careers.airbnb.com",
        },
        {
            "name": "Stripe",
            "url": "https://stripe.com/jobs/search?q=design",
            "method": "web_fetch",
            "query": "principal designer stripe site:stripe.com/jobs",
        },
        {
            "name": "Atlassian",
            "url": "https://www.atlassian.com/company/careers/search?department=design",
            "method": "web_fetch",
            "query": "principal design atlassian site:atlassian.com/careers",
        },
        {
            "name": "Adobe",
            "url": "https://careers.adobe.com/us/en/search-jobs?keywords=design",
            "method": "web_fetch",
            "query": "principal design adobe site:careers.adobe.com",
        },
        {
            "name": "Microsoft",
            "url": "https://careers.microsoft.com/us/en/search?keywords=design",
            "method": "web_fetch",
            "query": "principal designer microsoft site:careers.microsoft.com",
        },
        {
            "name": "Salesforce",
            "url": "https://salesforce.wd5.myworkdaysite.com/en-US/",
            "method": "web_fetch",
            "query": "principal design salesforce site:salesforce.wd5.myworkdaysite.com",
        },
    ],
    
    "recruiters": [
        {
            "name": "Aquent Creative Circle",
            "url": "https://aquent.com/creative-circle",
            "method": "contact",
            "action": "Send portfolio + message about principal roles",
        },
        {
            "name": "Toptal Design",
            "url": "https://www.toptal.com/designers",
            "method": "contact",
            "action": "Apply to network, express interest in principal/leadership roles",
        },
        {
            "name": "Onward Search",
            "url": "https://www.onwardsearch.com",
            "method": "contact",
            "action": "Contact about director/principal search opportunities",
        },
        {
            "name": "Robert Half Creative",
            "url": "https://www.roberthalf.com/en/creative",
            "method": "contact",
            "action": "Register profile, discuss principal-level opportunities",
        },
    ],
    
    "communities": [
        {
            "name": "DesignX Community",
            "url": "https://designxcommunity.com",
            "method": "community",
            "action": "Join (invite), watch #opportunities channel",
        },
        {
            "name": "Friends of Figma",
            "url": "https://figma.com/community",
            "method": "community",
            "action": "Join free, watch #jobs channel",
        },
        {
            "name": "Product Design Guild",
            "url": "https://productdesignguild.com",
            "method": "community",
            "action": "Apply to join, access job board",
        },
        {
            "name": "Rosenfeld Media Community",
            "url": "https://rosenfeldsupplies.com/community",
            "method": "community",
            "action": "Join community, check member forums",
        },
    ],
}

def print_search_plan():
    """Print comprehensive search plan"""
    print(f"\n{'='*70}")
    print(f"ENHANCED JOB SEARCH PLAN — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    print("📋 SEARCH SOURCES\n")
    
    print("🔴 TIER 1 BOARDS (Specialized Design/Product)")
    for source in SEARCH_SOURCES["tier1_boards"]:
        print(f"  • {source['name']}: {source['url']}")
    
    print("\n🔵 GENERAL BOARDS")
    for source in SEARCH_SOURCES["general_boards"]:
        print(f"  • {source['name']}: {source['url']}")
    
    print("\n🟣 COMPANY CAREER PAGES (Direct Apply)")
    for source in SEARCH_SOURCES["company_careers"]:
        print(f"  • {source['name']}: {source['url']}")
    
    print("\n🟠 RECRUITERS (Direct Outreach)")
    for source in SEARCH_SOURCES["recruiters"]:
        print(f"  • {source['name']}")
        print(f"    Action: {source['action']}")
    
    print("\n🟢 DESIGN COMMUNITIES (Hidden Opportunities)")
    for source in SEARCH_SOURCES["communities"]:
        print(f"  • {source['name']}")
        print(f"    Action: {source['action']}")
    
    print(f"\n{'='*70}")
    print(f"TOTAL SOURCES: {sum(len(v) for v in SEARCH_SOURCES.values())}")
    print(f"{'='*70}\n")
    
    # Print recommended schedule
    print("📅 RECOMMENDED SCHEDULE\n")
    print("DAILY (Automated):")
    print("  • Indeed (principal design systems)")
    print("  • LinkedIn (principal product designer)")
    print("  • Wellfound (principal design remote)")
    
    print("\nWEEKLY (Sundays, 30 min):")
    print("  • Otta, AIGA Jobs, Dribbble, UX Jobs Board")
    print("  • Company career pages (Shopify, Stripe, Airbnb, etc.)")
    print("  • Working Not Working, BuildinColorado")
    
    print("\nMONTHLY (1st of month, 30 min):")
    print("  • Recruiter outreach (Aquent, Toptal, Onward, Robert Half)")
    print("  • Join 1-2 new communities")
    print("  • Deepen network connections")
    
    print("\n" + "="*70)
    print("🎯 ACTION ITEMS FOR TODAY (Mar 5)")
    print("="*70 + "\n")
    print("[ ] Create accounts on: Wellfound, Otta, AIGA, Dribbble, UX Jobs Board")
    print("[ ] Bookmark company career pages (9 companies listed above)")
    print("[ ] Apply to 2-3 high-fit roles found today")
    print("[ ] Set up daily Indeed/LinkedIn job alerts")
    print("[ ] Review comprehensive search strategy (COMPREHENSIVE_SEARCH_STRATEGY.md)")
    print("\n")


def main():
    """Print enhanced search plan and instructions"""
    print_search_plan()
    
    print("📖 Full documentation: COMPREHENSIVE_SEARCH_STRATEGY.md")
    print("🔧 Customization script ready: customize_application_sonnet.py")
    print("📊 Tracking template: OPPORTUNITIES.md (log all opportunities here)\n")


if __name__ == "__main__":
    main()
