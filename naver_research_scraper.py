import requests
# pyrefly: ignore [missing-import]
from bs4 import BeautifulSoup
import os
import logging
import re
from datetime import datetime
from pathlib import Path
import time
import config

logger = logging.getLogger(__name__)

class NaverResearchScraper:
    """네이버 증권 리서치 보고서 수집기"""
    
    def __init__(self):
        self.base_url = "https://finance.naver.com/research/"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        self.output_dir = Path(config.NAVER_RESEARCH_SOURCE_DIR)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def fetch_report_list(self, category_file: str) -> list[dict]:
        """특정 카테고리의 리포트 목록을 가져옴"""
        url = f"{self.base_url}{category_file}"
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            # 네이버 금융은 EUC-KR 또는 CP949를 사용하는 경우가 많음
            response.encoding = response.apparent_encoding or "euc-kr"
            
            soup = BeautifulSoup(response.text, "html.parser")
            table = soup.select_one("table.type_1")
            if not table:
                return []
                
            reports = []
            rows = table.select("tr")
            for row in rows:
                # 상세 페이지 링크가 있는 행만 처리
                title_elem = row.select_one("a[href*='_read.naver']")
                if not title_elem:
                    continue
                
                cols = row.select("td")
                if not cols:
                    continue
                    
                title = title_elem.get_text(strip=True)
                detail_link = title_elem.get("href")
                firm = cols[1].get_text(strip=True)
                
                # 날짜 열 찾기 (보통 마지막 열 부근)
                date = ""
                for col in reversed(cols):
                    txt = col.get_text(strip=True)
                    if re.match(r"\d{2}\.\d{2}\.\d{2}", txt):
                        date = txt
                        break
                
                # PDF 링크 확인 (클래스가 file인 td 내부의 a 태그)
                pdf_elem = row.select_one("td.file a")
                pdf_link = pdf_elem.get("href") if pdf_elem else None
                
                # nid 추출
                import urllib.parse
                parsed = urllib.parse.urlparse(detail_link)
                params = urllib.parse.parse_qs(parsed.query)
                nid = params.get("nid", [None])[0]
                
                if nid:
                    reports.append({
                        "title": title,
                        "firm": firm,
                        "date": date,
                        "detail_link": f"{self.base_url}{detail_link}",
                        "pdf_link": pdf_link,
                        "nid": nid
                    })
                    logger.debug(f"Found report: {title} ({firm}, {date})")
            
            return reports
        except Exception as e:
            logger.error(f"리포트 목록 조회 실패 ({category_file}): {e}")
            return []

    def fetch_report_detail(self, detail_url: str) -> str:
        """리포트 상세 페이지에서 요약 텍스트 추출"""
        try:
            response = requests.get(detail_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or "euc-kr"
            
            soup = BeautifulSoup(response.text, "html.parser")
            summary_elem = soup.select_one(".view_cnt")
            if summary_elem:
                return summary_elem.get_text("\n", strip=True)
            return ""
        except Exception as e:
            logger.error(f"리포트 상세 조회 실패 ({detail_url}): {e}")
            return ""

    def scrape_category(self, category_name: str, category_file: str):
        """특정 카테고리의 최신 리포트들을 수집 및 저장"""
        logger.info(f"🚀 네이버 리서치 수집 시작: {category_name}")
        reports = self.fetch_report_list(category_file)
        
        category_dir = self.output_dir / category_name
        category_dir.mkdir(parents=True, exist_ok=True)
        
        count = 0
        for report in reports[:10]:  # 최신 10개만 확인
            nid = report["nid"]
            if not nid:
                continue
                
            filename = category_dir / f"{report['date'].replace('.', '')}_{nid}.txt"
            if filename.exists():
                continue
                
            # 상세 내용 가져오기
            summary = self.fetch_report_detail(report["detail_link"])
            
            # 파일 저장
            content = f"제목: {report['title']}\n"
            content += f"증권사: {report['firm']}\n"
            content += f"날짜: {report['date']}\n"
            content += f"PDF: {report['pdf_link']}\n"
            content += "-" * 50 + "\n"
            content += summary
            
            filename.write_text(content, encoding="utf-8")
            count += 1
            time.sleep(1)  # 서버 부하 방지
            
        logger.info(f"✅ {category_name} 수집 완료: {count}건 신규 저장")

    def scrape_all(self):
        """모든 카테고리 수집 실행"""
        for name, filename in config.NAVER_RESEARCH_CATEGORIES.items():
            self.scrape_category(name, filename)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = NaverResearchScraper()
    scraper.scrape_all()
