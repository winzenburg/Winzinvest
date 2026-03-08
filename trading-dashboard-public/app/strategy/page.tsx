'use client';

import Link from 'next/link';

export default function StrategyPage() {
  return (
    <div className="min-h-screen bg-stone-50">
      <div className="max-w-4xl mx-auto px-8 py-12">
        {/* Header */}
        <header className="mb-12 pb-6 border-b border-stone-200">
          <Link 
            href="/" 
            className="text-sm text-stone-500 hover:text-stone-700 mb-4 inline-block"
          >
            ← Back to Dashboard
          </Link>
          <h1 className="font-serif text-5xl font-bold text-slate-900 tracking-tight mt-4">
            Our Trading Strategy
          </h1>
          <p className="text-stone-500 mt-4 text-lg">
            How we use computers to trade stocks automatically
          </p>
        </header>

        {/* Content */}
        <div className="prose prose-stone max-w-none">
          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">
              What We Do
            </h2>
            <p className="text-stone-700 leading-relaxed mb-4">
              We built a computer system that buys and sells stocks automatically. Think of it like 
              a robot trader that follows strict rules we programmed. The robot never gets tired, 
              scared, or greedy—it just follows the plan.
            </p>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">
              How We Pick Stocks
            </h2>
            <p className="text-stone-700 leading-relaxed mb-4">
              Every day, our system looks at thousands of stocks and picks the best ones using 
              three main strategies:
            </p>
            
            <div className="space-y-6 mt-6">
              <div className="border-l-4 border-green-500 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-2">
                  1. Momentum Trading (Going Long)
                </h3>
                <p className="text-stone-700 leading-relaxed">
                  We buy stocks that are going up strongly. It's like joining a winning team—if a 
                  stock is already doing well and lots of people are buying it, we jump on board. 
                  We look for stocks that are above their average prices and have strong "relative 
                  strength" (meaning they're doing better than most other stocks).
                </p>
              </div>

              <div className="border-l-4 border-red-500 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-2">
                  2. Short Selling (Betting Against Weak Stocks)
                </h3>
                <p className="text-stone-700 leading-relaxed">
                  Sometimes we bet that a stock will go down. This is called "short selling." 
                  We look for stocks that are falling and showing weakness. If we're right and 
                  the stock drops, we make money. It's riskier than buying stocks, so we're 
                  extra careful with this strategy.
                </p>
              </div>

              <div className="border-l-4 border-orange-500 pl-6">
                <h3 className="text-xl font-bold text-slate-900 mb-2">
                  3. Mean Reversion (Bounce-Back Trading)
                </h3>
                <p className="text-stone-700 leading-relaxed">
                  When a good stock drops too quickly, it often bounces back up. We buy these 
                  temporarily oversold stocks and wait for them to recover. It's like buying 
                  something on sale—we know it's worth more, so we grab it while it's cheap.
                </p>
              </div>
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">
              How We Protect Our Money
            </h2>
            <p className="text-stone-700 leading-relaxed mb-4">
              The most important part of trading is not losing money. We have several safety rules:
            </p>
            
            <ul className="space-y-3 text-stone-700">
              <li className="flex items-start">
                <span className="text-green-600 font-bold mr-3">✓</span>
                <span>
                  <strong>Stop Losses:</strong> If a stock goes down too much (usually about 1-2%), 
                  we automatically sell it. This prevents small losses from becoming big losses.
                </span>
              </li>
              <li className="flex items-start">
                <span className="text-green-600 font-bold mr-3">✓</span>
                <span>
                  <strong>Position Sizing:</strong> We never put more than 5% of our money into 
                  any single stock. This way, if one stock fails, it doesn't hurt us too badly.
                </span>
              </li>
              <li className="flex items-start">
                <span className="text-green-600 font-bold mr-3">✓</span>
                <span>
                  <strong>Daily Loss Limit:</strong> If we lose 3% of our account in one day, 
                  the system stops trading until the next day. This prevents bad days from 
                  becoming terrible days.
                </span>
              </li>
              <li className="flex items-start">
                <span className="text-green-600 font-bold mr-3">✓</span>
                <span>
                  <strong>Diversification:</strong> We spread our money across different types 
                  of companies (tech, healthcare, finance, etc.). If one industry has a bad day, 
                  the others might still do well.
                </span>
              </li>
            </ul>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">
              Using Leverage (Borrowed Money)
            </h2>
            <p className="text-stone-700 leading-relaxed mb-4">
              Our broker (Interactive Brokers) lets us borrow money to trade with. This is called 
              "leverage." If we have $100,000, they might let us trade as if we have $200,000. 
              This can make our profits bigger, but it also makes losses bigger, so we use it 
              carefully.
            </p>
            <p className="text-stone-700 leading-relaxed">
              We currently use <strong>2x leverage</strong>, which means we can control twice as 
              much stock as the cash we actually have. But remember—our safety rules (like daily 
              loss limits) are based on our real money, not the borrowed amount.
            </p>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">
              How the System Decides What to Trade
            </h2>
            <p className="text-stone-700 leading-relaxed mb-4">
              Every day, our system runs a "screener" that checks thousands of stocks. It's 
              looking for specific patterns:
            </p>
            
            <div className="bg-stone-50 border border-stone-200 rounded-lg p-6 mb-4">
              <h4 className="font-bold text-slate-900 mb-3">For Long Positions (Buying):</h4>
              <ul className="space-y-2 text-stone-700 text-sm">
                <li>• Stock price is above its 50-day and 200-day moving averages</li>
                <li>• Relative strength is positive (beating the market)</li>
                <li>• Volume is higher than normal (lots of people are buying)</li>
                <li>• The stock has enough liquidity (easy to buy and sell)</li>
              </ul>
            </div>

            <div className="bg-stone-50 border border-stone-200 rounded-lg p-6">
              <h4 className="font-bold text-slate-900 mb-3">For Short Positions (Selling):</h4>
              <ul className="space-y-2 text-stone-700 text-sm">
                <li>• Stock price is below its moving averages</li>
                <li>• Relative strength is negative (losing to the market)</li>
                <li>• Volume shows selling pressure</li>
                <li>• The stock is in a clear downtrend</li>
              </ul>
            </div>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">
              When We Exit Trades
            </h2>
            <p className="text-stone-700 leading-relaxed mb-4">
              We don't just buy and hope for the best. We have clear rules for when to sell:
            </p>
            
            <ul className="space-y-3 text-stone-700">
              <li>
                <strong>Take Profit:</strong> When a stock goes up by our target amount (usually 
                1.5-3x the stock's normal daily movement), we sell and lock in the profit.
              </li>
              <li>
                <strong>Stop Loss:</strong> If the stock goes down by our limit (usually 1-2x 
                the normal daily movement), we sell to prevent bigger losses.
              </li>
              <li>
                <strong>Signal Reversal:</strong> If our indicators show the trend is changing, 
                we exit even if we haven't hit our profit or loss targets.
              </li>
              <li>
                <strong>Time Limit:</strong> Some strategies have time limits. For example, 
                mean reversion trades might only last a few days.
              </li>
            </ul>
          </div>

          <div className="bg-white border border-stone-200 rounded-xl p-8 mb-8">
            <h2 className="text-2xl font-serif font-bold text-slate-900 mb-4">
              Why This Works
            </h2>
            <p className="text-stone-700 leading-relaxed mb-4">
              Our strategy works because:
            </p>
            
            <ol className="space-y-3 text-stone-700 list-decimal list-inside">
              <li>
                <strong>Discipline:</strong> The computer follows the rules perfectly every time. 
                It doesn't get emotional or make impulsive decisions.
              </li>
              <li>
                <strong>Speed:</strong> The system can analyze thousands of stocks in seconds and 
                place trades instantly when opportunities appear.
              </li>
              <li>
                <strong>Risk Management:</strong> We always know exactly how much we could lose 
                on every trade, and we never risk too much.
              </li>
              <li>
                <strong>Consistency:</strong> We trade the same way every day, which means our 
                results are predictable over time.
              </li>
            </ol>
          </div>

          <div className="bg-amber-50 border border-amber-200 rounded-xl p-8">
            <h2 className="text-2xl font-serif font-bold text-amber-900 mb-4">
              Important Disclaimer
            </h2>
            <p className="text-amber-800 leading-relaxed">
              Trading stocks is risky. Even with good strategies and safety rules, we can still 
              lose money. Past performance doesn't guarantee future results. This system is 
              designed to manage risk carefully, but there's no such thing as a "sure thing" 
              in trading. Never invest money you can't afford to lose.
            </p>
          </div>
        </div>

        {/* Footer */}
        <footer className="mt-16 pt-8 border-t border-stone-200 text-center text-sm text-stone-400">
          <p>Mission Control Trading System</p>
        </footer>
      </div>
    </div>
  );
}
