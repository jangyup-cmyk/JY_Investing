import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """모든 에이전트의 기본 클래스"""
    
    def __init__(self, name: str):
        self.name = name
        self.execution_count = 0
        self.success_count = 0
        self.last_result = None
        self.created_at = datetime.now()
    
    @abstractmethod
    def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        입력 데이터를 처리하고 결과를 반환
        
        Args:
            input_data: 처리할 입력 데이터
            
        Returns:
            처리 결과 딕셔너리
        """
        pass
    
    def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """에이전트 실행 및 메트릭 기록"""
        try:
            logger.info(f"[{self.name}] 실행 시작")
            self.execution_count += 1
            
            result = self.process(input_data)
            result["agent"] = self.name
            result["executed_at"] = datetime.now().isoformat()
            result["success"] = True
            
            self.success_count += 1
            self.last_result = result
            
            logger.info(f"[{self.name}] 실행 성공")
            return result
            
        except Exception as e:
            logger.error(f"[{self.name}] 실행 오류: {e}")
            return {
                "agent": self.name,
                "success": False,
                "error": str(e),
                "executed_at": datetime.now().isoformat()
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """에이전트 통계 반환"""
        success_rate = (self.success_count / self.execution_count * 100) if self.execution_count > 0 else 0
        return {
            "name": self.name,
            "execution_count": self.execution_count,
            "success_count": self.success_count,
            "success_rate": f"{success_rate:.1f}%",
            "created_at": self.created_at.isoformat()
        }
