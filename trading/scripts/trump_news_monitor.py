#!/usr/bin/env python3
"""
Trump Policy News Monitor
Tracks X (@realDonaldTrump) and Truth Social posts
Alerts on market-moving announcements: tariffs, trade, taxes, Fed policy

Runs: Every 5 minutes during trading hours
Alerts: Telegram with market impact assessment
"""

import os
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import requests
from enum import Enum

class MarketImpact(Enum):
    CRITICAL = "🚨 CRITICAL"  # Immediate trading halt needed
    HIGH = "⚠️ HIGH"           # Potential position adjustment needed
    MEDIUM = "📢 MEDIUM"       # Monitor closely, may affect sector rotation
    LOW = "📌 LOW"             # General interest, monitor

class TrumpNewsMonitor:
    def __init__(self):
        self.trading_dir = Path(__file__).resolve().parents[1]
        self.log_file = self.trading_dir / 'logs' / 'trump_news.json'
        self.log_file.parent.mkdir(exist_ok=True)
        
        # Telegram config
        self.telegram_bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.telegram_chat_id = os.getenv('TELEGRAM_CHAT_ID')
        
        # Keywords to monitor (market-moving policy areas)
        self.keywords = {
            'tariffs': {
                'terms': ['tariff', 'tariffs', 'import tax', 'trade war', 'china tariff'],
                'impact': MarketImpact.CRITICAL,
                'sectors': ['Technology', 'Manufacturing', 'Consumer', 'Energy']
            },
            'trade_policy': {
                'terms': ['trade deal', 'trade agreement', 'trade war', 'nafta', 'usmca', 'wto'],
                'impact': MarketImpact.HIGH,
                'sectors': ['Manufacturing', 'Energy', 'Agriculture', 'Technology']
            },
            'taxes': {
                'terms': ['tax cut', 'tax reform', 'corporate tax', 'capital gains', 'tax rate'],
                'impact': MarketImpact.HIGH,
                'sectors': ['All sectors']
            },
            'fed_policy': {
                'terms': ['fed should', 'interest rates', 'fed policy', 'rate cut', 'rate hike', 'jerome powell'],
                'impact': MarketImpact.CRITICAL,
                'sectors': ['All sectors']
            },
            'deregulation': {
                'terms': ['deregulation', 'regulations', 'epa', 'sec rule', 'environmental'],
                'impact': MarketImpact.MEDIUM,
                'sectors': ['Energy', 'Manufacturing', 'Finance', 'Healthcare']
            },
            'stimulus': {
                'terms': ['stimulus', 'infrastructure', 'spending bill', 'jobs program'],
                'impact': MarketImpact.HIGH,
                'sectors': ['Construction', 'Energy', 'Technology']
            },
            'market_comment': {
                'terms': ['stock market', 'market crash', 'market surge', 'dow', 'nasdaq', 'sp500'],
                'impact': MarketImpact.MEDIUM,
                'sectors': ['All sectors']
            }
        }
    
    def load_history(self):
        """Load previously seen posts"""
        if self.log_file.exists():
            return json.loads(self.log_file.read_text())
        return {
            'last_check': None,
            'posts': []
        }
    
    def save_history(self, history):
        """Save post history"""
        self.log_file.write_text(json.dumps(history, indent=2))
    
    def classify_impact(self, post_text):
        """Determine market impact level"""
        text_lower = post_text.lower()
        highest_impact = MarketImpact.LOW
        matching_keywords = []
        
        for category, config in self.keywords.items():
            for term in config['terms']:
                if term.lower() in text_lower:
                    matching_keywords.append((category, config['impact']))
                    if config['impact'].value.startswith('🚨'):
                        highest_impact = MarketImpact.CRITICAL
                    elif highest_impact != MarketImpact.CRITICAL and config['impact'].value.startswith('⚠️'):
                        highest_impact = MarketImpact.HIGH
        
        return highest_impact, matching_keywords
    
    def generate_alert(self, post_data, impact_level, keywords):
        """Generate Telegram alert"""
        impact_emoji = {
            MarketImpact.CRITICAL: "🚨",
            MarketImpact.HIGH: "⚠️",
            MarketImpact.MEDIUM: "📢",
            MarketImpact.LOW: "📌"
        }
        
        emoji = impact_emoji.get(impact_level, "📰")
        timestamp = datetime.now().strftime("%I:%M %p MT")
        
        # Extract key topics
        topics = set([kw[0].replace('_', ' ').title() for kw in keywords])
        
        alert = f"""{emoji} {impact_level.value} - Trump Policy Alert

📝 Post: {post_data.get('text', '')[:200]}...

🎯 Topics: {', '.join(topics)}
⏰ Time: {timestamp}
📱 Source: {post_data.get('source', 'Unknown')}

🔄 Action Recommended:
- Check affected sectors: Tech, Finance, Energy, Manufacturing
- Monitor position exposure to tariff-sensitive stocks
- Be ready to adjust if market gaps on open
- Watch sector rotation patterns
"""
        
        return alert
    
    def send_telegram_alert(self, alert_text):
        """Send alert via Telegram"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            print("❌ Telegram config missing")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
            response = requests.post(
                url,
                json={
                    "chat_id": self.telegram_chat_id,
                    "text": alert_text,
                    "parse_mode": "HTML"
                },
                timeout=10
            )
            
            if response.status_code == 200:
                print("✅ Alert sent to Telegram")
                return True
            else:
                print(f"❌ Telegram error: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Error sending alert: {e}")
            return False
    
    def monitor_x_api(self):
        """
        Monitor X (Twitter) for Trump posts
        Requires: Twitter API v2 Bearer Token
        """
        # TODO: Implement with Twitter API v2
        # Bearer token from: https://developer.twitter.com/
        # Endpoint: /2/tweets/search/recent with query: from:@realDonaldTrump
        
        print("⚠️  X monitoring requires Twitter API v2 setup")
        print("   Steps:")
        print("   1. Get Twitter API key from https://developer.twitter.com/")
        print("   2. Store in .env as TWITTER_BEARER_TOKEN")
        print("   3. Query: from:@realDonaldTrump -is:retweet")
        return []
    
    def monitor_truth_social_api(self):
        """
        Monitor Truth Social for Trump posts
        Requires: Truth Social API access or web scraping
        """
        # TODO: Implement with Truth Social API or beautifulsoup
        # Truth Social account: @realDonaldTrump
        # Base URL: https://truthsocial.com/@realDonaldTrump
        
        print("⚠️  Truth Social monitoring requires web scraping setup")
        print("   Steps:")
        print("   1. Use beautifulsoup + requests for web scraping")
        print("   2. Monitor: https://truthsocial.com/@realDonaldTrump")
        print("   3. Check every 5 minutes during market hours")
        return []
    
    def monitor_rss_feeds(self):
        """
        Monitor RSS/webhooks for policy news
        More reliable than direct API monitoring
        """
        # Alternative: Monitor news aggregators
        sources = {
            'policy_announcements': 'https://www.whitehouse.gov/feed/',
            'trump_news': 'https://www.newsmax.com/feed/',  # Example
            'tariff_news': 'https://www.cnbc.com/id/100003114/news/',  # Trade news
        }
        
        # In production, implement RSS parsing
        print("⚠️  RSS feed monitoring requires feedparser setup")
        return []
    
    def check_manually(self):
        """
        Placeholder for manual checking
        User will manually check X/Truth Social and copy posts
        """
        print("""
        📋 Manual Monitoring Setup
        
        Since API access requires setup, you can:
        1. Check X daily: https://twitter.com/realDonaldTrump
        2. Check Truth Social: https://truthsocial.com/@realDonaldTrump
        3. Copy any market-moving posts here
        4. I'll classify impact and send alerts
        
        Or set up proper API monitoring:
        - Twitter API v2: https://developer.twitter.com/
        - Truth Social API/scraping: Requires third-party library
        """)
    
    def run(self):
        """Main monitoring loop"""
        print("🚀 Trump News Monitor Starting")
        print("⏰ Checking every 5 minutes during market hours")
        print("")
        
        # Monitor sources
        x_posts = self.monitor_x_api()
        truth_posts = self.monitor_truth_social_api()
        rss_posts = self.monitor_rss_feeds()
        
        # For now, use manual checking
        self.check_manually()
        
        # Log status
        status = {
            'timestamp': datetime.now().isoformat(),
            'x_checked': len(x_posts) > 0,
            'truth_social_checked': len(truth_posts) > 0,
            'rss_checked': len(rss_posts) > 0,
            'alerts_sent': 0
        }
        
        print(f"\n✅ Monitor status: {json.dumps(status, indent=2)}")
        
        return status

if __name__ == "__main__":
    monitor = TrumpNewsMonitor()
    monitor.run()
