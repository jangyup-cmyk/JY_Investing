# Deep Interview Spec: Telegram Theme-Linked Auto-Trading Program

## Metadata
- **Profile**: standard
- **Rounds**: 5
- **Final Ambiguity**: 0.08
- **Threshold**: 0.2
- **Context Type**: greenfield
- **Context Snapshot**: `.omx/context/telegram-auto-trading-20260509T134606Z.md`

## Clarity Breakdown
| Dimension | Score |
| --- | --- |
| Intent | 0.95 |
| Outcome | 0.90 |
| Scope | 0.90 |
| Constraints | 0.90 |
| Success | 0.85 |

## Intent
The user wants to create an automated stock trading program that combines AI-driven social sentiment (Telegram themes) with rigorous technical chart analysis to execute trades automatically on the Korean stock market (KIS API).

## Desired Outcome
- A web-based dashboard (Flask) running on AWS EC2.
- A 5-agent AI pipeline that debates and decides on the "Top 3 Themes" daily.
- A 100% automated trading engine that executes trades for a single account based on a weighted scoring system of 13 technical indicators.
- Personalized Telegram notifications via individual bots.

## In-Scope (MVP)
- **AI Theme Discovery**: 5-agent workflow (Noise Removal -> Analysis -> Debate -> Decision).
- **Single Account Trading**: Full automation for one account via KIS API.
- **Weighted Scoring**: Implementation of 13 indicators with a total score threshold for BUY signals.
- **Order Management**: 50% Market / 50% Limit split, 10-minute auto-cancel for unfilled orders.
- **Web GUI**: Basic control and monitoring dashboard.
- **Telegram Notifications**: Individual bot tokens/channel IDs per user.

## Out-of-Scope (Non-goals)
- **Mobile APP**: Postponed for future versions.
- **Multi-account Trading**: MVP will focus on a single account first.
- **Complex UI**: Dashboard will be functional but simple (MVP style).

## Decision Boundaries
- **AI/Automation**: 100% automated execution when criteria are met; no manual approval required.
- **Scoring**: Trades are triggered when the weighted sum of 13 indicators exceeds a threshold (to be defined in planning).

## Constraints
- **Hardware**: AWS EC2 t2.micro (requires lightweight implementation).
- **Broker**: 한국투자증권 (Korea Investment & Securities) API.
- **Tech Stack**: Python (Flask, pandas, TA-Lib, APScheduler, python-telegram-bot).

## Success Criteria
- Successful extraction of Top 3 themes from Telegram messages daily.
- Automated execution of trades (Buy/Sell) based on the combined AI + Technical signals.
- Consistent delivery of personalized Telegram reports.
- System stability on t2.micro.

## Pressure Pass Findings
- The original "13 conditions" requirement was refined from a "must meet all" to a "weighted scoring system," allowing for more flexibility and realistic trading conditions while maintaining rigor.

## Next Steps
- Use the provided prompt for `$ralplan` to design the architecture and test plan.
