# JY 투자클럽 에이전트 흐름 다이어그램

이 문서는 `docs/README_AGENT.md`에 정의된 멀티-에이전트 팀 구조를 기반으로 한 실제 흐름 다이어그램과 코드 구조를 설명합니다.

## 에이전트 흐름 다이어그램

아래는 Mermaid 형식의 다이어그램으로, 텔레그램 테마 신호부터 최종 매매 실행까지의 에이전트 간 상호작용을 보여줍니다.

```mermaid
graph TD
    A[텔레그램 메시지 수집] --> B[Sentiment Analyst]
    B --> C[테마 분석 및 후보 선별]
    C --> D[Technical Analyst]
    D --> E[13대 필터 검증]
    E --> F[Researcher Team]
    F --> G[Bull/Bear 토론 및 리스크 평가]
    G --> H[Risk Management]
    H --> I[시장 지수, VI, 시간대 등 안전성 확인]
    I --> J[Trader Agent]
    J --> K[50% 시장가 + 50% 지정가 주문 실행]
    K --> L[10분 후 미체결 취소]
    L --> M[Portfolio Manager]
    M --> N[최종 승인/거부 및 정책 적용]
    N --> O[Telegram 알림 전송]

    style A fill:#e1f5fe
    style B fill:#b3e5fc
    style D fill:#81d4fa
    style F fill:#4fc3f7
    style H fill:#29b6f6
    style J fill:#03a9f4
    style M fill:#0277bd
```

### 다이어그램 설명

- **Sentiment Analyst**: 텔레그램 데이터를 분석해 초기 테마 후보를 생성합니다.
- **Technical Analyst**: `analyzer.py`의 필터로 기술적 유효성을 검증합니다.
- **Researcher Team**: Bull/Bear 관점으로 재평가하며, 리스크를 강조합니다.
- **Risk Management**: 실시간 모니터링으로 안전성을 보장합니다.
- **Trader Agent**: `trader.py`에서 주문을 실행합니다.
- **Portfolio Manager**: 최종 정책 적용 (현재는 Trader Agent에 통합 가능).

## 코드 구조 제안

각 에이전트를 클래스로 구현하여 모듈화합니다. `agents/` 폴더에 배치합니다.

### 1. Base Agent 클래스 (`agents/base_agent.py`)

```python
from abc import ABC, abstractmethod

class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def process(self, input_data: dict) -> dict:
        pass
```

### 2. Sentiment Analyst (`agents/sentiment_analyst.py`)

```python
from agents.base_agent import BaseAgent
import theme_db

class SentimentAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("Sentiment Analyst")

    def process(self, input_data: dict) -> dict:
        # 텔레그램 메시지 분석 및 테마 추출
        themes = theme_db.get_themes_for_code(input_data.get("stock_code", ""))
        return {"themes": themes, "sentiment_score": 0.8}  # 예시
```

### 3. Technical Analyst (`agents/technical_analyst.py`)

```python
from agents.base_agent import BaseAgent
import analyzer

class TechnicalAnalyst(BaseAgent):
    def __init__(self):
        super().__init__("Technical Analyst")

    def process(self, input_data: dict) -> dict:
        # 13대 필터 검증
        result = analyzer.is_valid_stock_final(
            stock=input_data["stock"],
            open_price=input_data["open_price"],
            high_price=input_data["high_price"],
            prev_close=input_data["prev_close"],
            daily_prices=input_data["daily_prices"],
            daily_opens=input_data["daily_opens"],
            daily_closes=input_data["daily_closes"],
            daily_volumes=input_data["daily_volumes"],
            minute_vols=input_data["minute_vols"],
            user=input_data["user"],
            token=input_data["token"]
        )
        return result
```

### 4. Researcher Team (`agents/researcher_team.py`)

```python
from agents.base_agent import BaseAgent

class ResearcherTeam(BaseAgent):
    def __init__(self):
        super().__init__("Researcher Team")

    def process(self, input_data: dict) -> dict:
        # Bull/Bear 토론 시뮬레이션 (간단한 규칙 기반)
        bull_score = input_data.get("technical_pass", False) and input_data.get("sentiment_score", 0) > 0.7
        bear_score = input_data.get("vi_safe", True) and input_data.get("market_bullish", True)
        return {"bull_approved": bull_score, "bear_approved": bear_score, "final_decision": bull_score and bear_score}
```

### 5. Risk Management (`agents/risk_management.py`)

```python
from agents.base_agent import BaseAgent
import analyzer

class RiskManagement(BaseAgent):
    def __init__(self):
        super().__init__("Risk Management")

    def process(self, input_data: dict) -> dict:
        # 리스크 체크
        time_ok = analyzer.is_valid_trading_time()["ok"]
        market_ok = input_data.get("market_bullish", False)
        return {"risk_pass": time_ok and market_ok}
```

### 6. Trader Agent (`agents/trader_agent.py`)

```python
from agents.base_agent import BaseAgent
import trader

class TraderAgent(BaseAgent):
    def __init__(self):
        super().__init__("Trader Agent")

    def process(self, input_data: dict) -> dict:
        # 주문 실행
        result = trader.execute_split_buy(
            user=input_data["user"],
            stock_code=input_data["stock"]["code"],
            current_price=input_data["stock"]["price"]
        )
        return {"trade_result": result}
```

### 7. Portfolio Manager (`agents/portfolio_manager.py`)

```python
from agents.base_agent import BaseAgent

class PortfolioManager(BaseAgent):
    def __init__(self):
        super().__init__("Portfolio Manager")

    def process(self, input_data: dict) -> dict:
        # 최종 승인 (현재는 Trader 결과 기반)
        trade_ok = input_data.get("trade_result") is not None
        return {"final_approval": trade_ok}
```

### 통합 실행 예시 (`agents/agent_orchestrator.py`)

```python
from agents.sentiment_analyst import SentimentAnalyst
from agents.technical_analyst import TechnicalAnalyst
from agents.researcher_team import ResearcherTeam
from agents.risk_management import RiskManagement
from agents.trader_agent import TraderAgent
from agents.portfolio_manager import PortfolioManager

class AgentOrchestrator:
    def __init__(self):
        self.agents = {
            "sentiment": SentimentAnalyst(),
            "technical": TechnicalAnalyst(),
            "researcher": ResearcherTeam(),
            "risk": RiskManagement(),
            "trader": TraderAgent(),
            "portfolio": PortfolioManager(),
        }

    def run_flow(self, input_data: dict) -> dict:
        # 흐름 실행
        sentiment_result = self.agents["sentiment"].process(input_data)
        technical_result = self.agents["technical"].process({**input_data, **sentiment_result})
        researcher_result = self.agents["researcher"].process(technical_result)
        risk_result = self.agents["risk"].process(researcher_result)
        trader_result = self.agents["trader"].process({**input_data, **risk_result})
        portfolio_result = self.agents["portfolio"].process(trader_result)
        return portfolio_result
```

이 구조를 `agents/` 폴더에 구현하면, 각 에이전트가 독립적으로 작동하며 확장 가능합니다. 필요 시 실제 LLM 통합으로 업그레이드할 수 있습니다.
