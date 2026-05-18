document.addEventListener('DOMContentLoaded', () => {
    const FAST_POLL_MS = 5000;
    const SLOW_POLL_MS = 10000;

    const configContainer = document.getElementById('config-container');
    const balanceContainer = document.getElementById('balance-container');
    const positionsBody = document.getElementById('positions-body');
    const logContainer = document.getElementById('log-container');
    const refreshLogsBtn = document.getElementById('refresh-logs-btn');

    // 현재가 맵 (계좌잔고 응답에서 채움)
    let _priceMap = {};

    // 계좌 선택 상태 (null = 전체)
    let _selectedAccount = null;
    let _accountCount = 0;

    // System Status + main.py 제어 버튼 상태
    let _mainRunning = false;
    let _toggleBusy  = false;

    // 계좌 선택 / 해제 (카드 클릭)
    window.selectAccount = function(accountNo) {
        _selectedAccount = (accountNo === null || _selectedAccount === accountNo) ? null : accountNo;

        // 카드 선택 표시
        document.querySelectorAll('.metric-card[data-account]').forEach(card => {
            card.classList.toggle('selected', card.dataset.account === _selectedAccount);
        });

        // 포지션 헤더 뱃지
        const badge = document.getElementById('positions-account-filter');
        if (badge) badge.textContent = _selectedAccount ? `${_selectedAccount} 계좌` : '전체 계좌';

        // "전체 보기" 버튼 표시/숨김
        const allBtn = document.getElementById('account-all-btn');
        if (allBtn) allBtn.style.display = _selectedAccount ? 'inline-block' : 'none';

        // 계좌열 표시/숨김 (단일 계좌 선택 시 계좌열 숨김)
        document.querySelectorAll('.col-account').forEach(el => {
            el.classList.toggle('hidden', !!_selectedAccount);
        });

        // 성과 패널 헤더 뱃지 동기화
        const perfBadge = document.getElementById('performance-account-filter');
        if (perfBadge) perfBadge.textContent = _selectedAccount ? `${_selectedAccount} 계좌` : '전체 계좌';

        renderPositionsIfReady();
        updatePerformance();
    };

    function updateSystemStatus() {
        fetch('/api/system-status')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                _mainRunning = res.main_running;
                _updateToggleBtn();
                document.getElementById('scheduler-status').textContent = res.scheduler_running ? '✅ 가동 중' : '⚠️ 중지됨';
                document.getElementById('scheduler-status').style.color = res.scheduler_running ? 'var(--profit-color)' : 'var(--warn-color)';
                document.getElementById('tg-status').textContent = res.telegram_monitor ? '✅ 활성' : '⏸ 비활성';
                document.getElementById('naver-status').textContent = res.naver_research ? '✅ 활성' : '⏸ 비활성';
                document.getElementById('server-time').textContent = res.server_time;
            })
            .catch(err => console.error('System status fetch error:', err));
    }

    function _updateToggleBtn() {
        const btn  = document.getElementById('main-toggle-btn');
        const text = document.getElementById('main-status-text');
        if (!btn) return;
        if (_toggleBusy) {
            btn.textContent = '처리중...';
            btn.style.background = '#6b7280';
            btn.style.color = '#fff';
            btn.disabled = true;
            return;
        }
        btn.disabled = false;
        if (_mainRunning) {
            btn.textContent = '⏹ 시스템 중지';
            btn.style.background = 'rgba(239,68,68,0.15)';
            btn.style.color = 'var(--loss-color)';
            btn.style.border = '1px solid var(--loss-color)';
            text.textContent = '시스템 가동 중';
        } else {
            btn.textContent = '▶ 시스템 시작';
            btn.style.background = 'rgba(16,185,129,0.15)';
            btn.style.color = 'var(--profit-color)';
            btn.style.border = '1px solid var(--profit-color)';
            text.textContent = '시스템 중지됨';
        }
    }

    window.toggleMainSystem = function() {
        if (_toggleBusy) return;
        const action = _mainRunning ? '중지' : '시작';
        if (!confirm(`매매 시스템을 ${action}하시겠습니까?`)) return;
        _toggleBusy = true;
        _updateToggleBtn();
        const endpoint = _mainRunning ? '/api/system/stop' : '/api/system/start';
        fetch(endpoint, { method: 'POST' })
            .then(r => r.json())
            .then(r => {
                if (!r.success) { alert('오류: ' + (r.error || '알 수 없는 오류')); }
                else { setTimeout(updateSystemStatus, 1500); }
            })
            .catch(() => alert('서버 통신 오류'))
            .finally(() => { _toggleBusy = false; _updateToggleBtn(); });
    };

    // AI Costs
    function updateAiCosts() {
        fetch('/api/ai-costs')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                const body = document.getElementById('ai-cost-body');
                const totalEl = document.getElementById('ai-cost-total');
                totalEl.textContent = `총 $${res.total_cost_usd.toFixed(2)} USD | ${(res.total_tokens / 1_000_000).toFixed(1)}M 토큰`;
                if (res.rows.length === 0) {
                    body.innerHTML = `<tr><td colspan="7" class="text-center" style="color:var(--text-secondary)">데이터 없음</td></tr>`;
                    return;
                }
                body.innerHTML = res.rows.map(r => `
                    <tr>
                        <td style="font-weight:600">${r.model}</td>
                        <td>${r.messages.toLocaleString()}</td>
                        <td style="color:var(--text-secondary)">${(r.input / 1000).toFixed(1)}K</td>
                        <td style="color:var(--text-secondary)">${(r.output / 1000).toFixed(1)}K</td>
                        <td style="color:var(--text-secondary)">${(r.cache_read / 1_000_000).toFixed(1)}M</td>
                        <td>${(r.total_tokens / 1_000_000).toFixed(2)}M</td>
                        <td style="color:var(--profit-color); font-weight:600">$${r.cost_usd.toFixed(4)}</td>
                    </tr>
                `).join('');
            })
            .catch(err => console.error('AI costs fetch error:', err));
    }

    // Config
    fetch('/api/config')
        .then(res => res.json())
        .then(data => {
            const wl = data.watch_list.length > 0 ? data.watch_list.join(', ') : '지정 안됨';
            configContainer.innerHTML = `
                <div class="config-item"><span class="label">모니터링 대상:</span> <span class="value">${wl}</span></div>
                <div class="config-item"><span class="label">손절(Stop Loss):</span> <span class="value">${(data.stop_loss_rate * 100).toFixed(1)}%</span></div>
                <div class="config-item"><span class="label">익절(Take Profit):</span> <span class="value">${(data.take_profit_rate * 100).toFixed(1)}%</span></div>
            `;
        })
        .catch(err => console.error('Config fetch error:', err));

    // Balance — 계좌별 카드 + 총합 요약 + 계좌 선택 필터
    function updateBalance() {
        fetch('/api/balance')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                _priceMap = {};
                _accountCount = res.data.length;

                // 현재가 맵 갱신
                res.data.forEach(b => {
                    (b.holdings || []).forEach(h => { if (h.code) _priceMap[h.code] = h; });
                });

                // ── 총합 요약 바 (계좌 2개 이상) ──────────────────────
                const summaryEl = document.getElementById('balance-summary');
                if (_accountCount >= 2) {
                    const totalEvalAll = res.data.reduce((s, b) => s + (b.total_eval_amount || 0), 0);
                    const totalBuyAll  = res.data.reduce((s, b) => s + (b.total_buy_amount  || 0), 0);
                    const pnlAll       = res.data.reduce((s, b) => s + (b.eval_profit_loss  || 0), 0);
                    const pnlRateAll   = totalBuyAll > 0 ? (pnlAll / totalBuyAll) * 100 : 0;
                    const pnlCol       = pnlAll >= 0 ? 'var(--profit-color)' : 'var(--loss-color)';
                    summaryEl.style.display = 'block';
                    summaryEl.innerHTML = `
                        <div class="balance-summary-row">
                            <span><span class="bs-label">전체 평가금액</span><span class="bs-value">₩ ${totalEvalAll.toLocaleString()}</span></span>
                            <span><span class="bs-label">전체 손익</span>
                                <span class="bs-value" style="color:${pnlCol}">
                                    ${pnlAll >= 0 ? '+' : ''}₩ ${pnlAll.toLocaleString()}
                                    (${pnlRateAll >= 0 ? '+' : ''}${pnlRateAll.toFixed(2)}%)
                                </span>
                            </span>
                            <span><span class="bs-label">계좌 수</span><span class="bs-value">${_accountCount}개</span></span>
                        </div>`;
                } else {
                    summaryEl.style.display = 'none';
                }

                // ── 계좌별 카드 렌더링 ─────────────────────────────────
                balanceContainer.innerHTML = '';
                res.data.forEach(b => {
                    if (b.error) {
                        balanceContainer.innerHTML += `
                            <div class="metric-card" data-account="${b.account}" onclick="selectAccount('${b.account}')">
                                <h3>${b.name}</h3>
                                <div class="value" style="color:var(--loss-color);font-size:1.2rem;">API 오류</div>
                                <div class="cell-sub">${b.error}</div>
                            </div>`;
                        return;
                    }
                    const totalEval = b.total_eval_amount || 0;
                    const totalBuy  = b.total_buy_amount  || 0;
                    const pnl       = b.eval_profit_loss != null ? b.eval_profit_loss : (totalEval - totalBuy);
                    const pnlRate   = totalBuy > 0 ? (pnl / totalBuy) * 100 : 0;
                    const pnlColor  = pnl > 0 ? 'var(--profit-color)' : (pnl < 0 ? 'var(--loss-color)' : 'var(--text-primary)');
                    const isSelected = _selectedAccount === b.account;
                    balanceContainer.innerHTML += `
                        <div class="metric-card${isSelected ? ' selected' : ''}" data-account="${b.account}" onclick="selectAccount('${b.account}')">
                            <h3 style="font-size:0.95rem;margin-bottom:0.25rem;">${b.name}</h3>
                            <div style="font-size:0.78rem;color:var(--text-secondary);margin-bottom:0.6rem;">${b.account}</div>
                            <div class="value" style="font-size:1.8rem;">₩ ${totalEval.toLocaleString()}</div>
                            <div class="cell-sub" style="margin-top:0.4rem;">주문가능 ₩ ${(b.available_balance || 0).toLocaleString()} | ${b.holdings_count || 0}종목</div>
                            <div style="margin-top:0.5rem;font-size:0.88rem;font-weight:600;color:${pnlColor};">
                                ${pnl >= 0 ? '+' : ''}₩ ${pnl.toLocaleString()}
                                <span style="font-size:0.8rem;">(${pnlRate >= 0 ? '+' : ''}${pnlRate.toFixed(2)}%)</span>
                            </div>
                        </div>`;
                });

                // 포지션 테이블 현재가 갱신
                renderPositionsIfReady();
            })
            .catch(err => console.error('Balance fetch error:', err));
    }

    // Positions — 계좌 필터 + 매수일 + 수익금액 표시
    let _positionsData = [];

    function renderPositionsIfReady() {
        if (_positionsData.length === 0) return;

        // 계좌 선택 시 해당 계좌만 필터
        const filtered = _positionsData[0] === '__empty__' ? [] :
            (_selectedAccount
                ? _positionsData.filter(p => p.account_no === _selectedAccount)
                : _positionsData);

        // colspan: 계좌열 숨김 여부에 따라 조정
        const colSpan = _selectedAccount ? 8 : 9;

        if (filtered.length === 0) {
            positionsBody.innerHTML = `<tr><td colspan="${colSpan}" class="text-center" style="color:var(--text-secondary)">
                ${_selectedAccount ? `${_selectedAccount} 계좌에 보유 포지션이 없습니다.` : '현재 보유 중인 포지션이 없습니다.'}
            </td></tr>`;
            return;
        }

        positionsBody.innerHTML = filtered.map(pos => {
            const p = _priceMap[pos.stock_code] || {};
            const curr = p.current_price || 0;
            const rate = p.pnl_rate != null ? p.pnl_rate : 0;
            const pnlAmt = p.pnl_amt != null ? p.pnl_amt : 0;
            const rateColor = rate > 0 ? 'var(--profit-color)' : (rate < 0 ? 'var(--loss-color)' : 'var(--text-secondary)');

            const currStr = curr > 0 ? `₩ ${curr.toLocaleString()}` : '-';

            // 수익률 + 수익금액 (2줄)
            const pnlStr = curr > 0
                ? `<div class="cell-main" style="color:${rateColor}">${rate >= 0 ? '+' : ''}${rate.toFixed(2)}%</div>
                   <div class="cell-sub" style="color:${rateColor}">${pnlAmt >= 0 ? '+' : ''}₩ ${pnlAmt.toLocaleString()}</div>`
                : '-';

            // 매수가 + 매수일자 (2줄) — buy_date 우선, 없으면 opened_at 날짜
            const buyDate = pos.buy_date || (pos.opened_at ? pos.opened_at.slice(0, 10) : '-');
            const buyStr = `<div class="cell-main">₩ ${Number(pos.buy_price).toLocaleString()}</div>
                            <div class="cell-sub">${buyDate}</div>`;

            const posKey = `${pos.account_no}_${pos.stock_code}`;
            const label  = `${pos.stock_name} (${pos.stock_code})`;
            const acctCell = _selectedAccount ? '' : `<td style="font-size:0.82rem;color:var(--text-secondary);">${pos.account_no}</td>`;

            return `
                <tr>
                    ${acctCell}
                    <td><span style="font-weight:600">${pos.stock_name}</span>
                        <span style="color:var(--text-secondary);font-size:0.78rem;"> (${pos.stock_code})</span></td>
                    <td>${buyStr}</td>
                    <td>${currStr}</td>
                    <td>${pnlStr}</td>
                    <td>${pos.qty.toLocaleString()} 주</td>
                    <td style="color:var(--loss-color)">₩ ${Number(pos.stop_loss).toLocaleString()}</td>
                    <td style="color:var(--profit-color)">₩ ${Number(pos.take_profit).toLocaleString()}</td>
                    <td><button class="btn-edit" onclick="openEditModal('${posKey}', ${pos.stop_loss}, ${pos.take_profit}, '${buyDate}', '${label}')">✏️</button></td>
                </tr>`;
        }).join('');
    }

    function updatePositions() {
        fetch('/api/positions')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                if (res.data.length === 0) {
                    _positionsData = ['__empty__'];
                } else {
                    _positionsData = res.data;
                }
                renderPositionsIfReady();
            })
            .catch(err => console.error('Positions fetch error:', err));
    }

    // Logs
    function updateLogs() {
        fetch('/api/logs')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                if (res.data.length === 0) {
                    logContainer.innerHTML = `<div class="log-entry">표시할 로그가 없습니다.</div>`;
                    return;
                }
                logContainer.innerHTML = res.data.map(log => {
                    const cls = log.level === 'ERROR' ? 'ERROR' : log.level === 'WARNING' ? 'WARNING' : 'INFO';
                    return `
                        <div class="log-entry">
                            <div class="log-time">${log.timestamp || '-'}</div>
                            <div class="log-level ${cls}">[${log.level}]</div>
                            <div class="log-msg"><span style="color:var(--text-secondary)">[${log.module}]</span> ${log.message}</div>
                        </div>
                    `;
                }).join('');
            })
            .catch(err => console.error('Logs fetch error:', err));
    }

    // AI Watchlist Report
    let _watchlistRefreshing = false;
    window.refreshWatchlist = function() {
        if (_watchlistRefreshing) return;
        _watchlistRefreshing = true;
        const btn = document.getElementById('watchlist-refresh-btn');
        if (btn) { btn.textContent = '⏳'; btn.disabled = true; }
        fetch('/api/watchlist-report/refresh', { method: 'POST' })
            .then(res => res.json())
            .then(res => {
                if (res.success) updateWatchlistReport();
                else alert('재생성 실패: ' + (res.error || '알 수 없는 오류'));
            })
            .catch(err => console.error('Watchlist refresh error:', err))
            .finally(() => {
                _watchlistRefreshing = false;
                if (btn) { btn.textContent = '↻'; btn.disabled = false; }
            });
    };

    function updateWatchlistReport() {
        fetch('/api/watchlist-report')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;

                // 메타 정보 (생성 시각 + 신선도 경고)
                const genAt = res.generated_at ? res.generated_at.replace('T', ' ').slice(0, 16) : '-';
                const genMs = res.generated_at ? Date.now() - new Date(res.generated_at).getTime() : 0;
                const stale = genMs > 2 * 60 * 60 * 1000; // 2시간 이상 오래된 경우
                document.getElementById('watchlist-meta').textContent =
                    `분석 텍스트 ${(res.text_count || 0).toLocaleString()}건 | 생성: ${genAt}${stale ? ' ⚠️' : ''}`;

                // 수동 지정 여부
                if (!res.auto_build && res.manual_watch_list.length > 0) {
                    document.getElementById('watchlist-manual').style.display = 'block';
                    document.getElementById('watchlist-manual-codes').textContent = res.manual_watch_list.join(', ');
                }

                // 추천 종목 점수 바 (종목명(코드) 형식)
                document.getElementById('watchlist-stocks').innerHTML = res.stocks.length === 0
                    ? '<div style="color:var(--text-secondary);font-size:0.85rem;grid-column:1/-1;">추출된 종목 없음</div>'
                    : res.stocks.map((s, i) => {
                        const themeStr = s.themes.slice(0, 3).join(' · ') || '-';
                        const barW = s.score_pct;
                        const rank = i + 1;
                        return `
                        <div style="margin-bottom:0.45rem;">
                            <div style="display:flex;justify-content:space-between;font-size:0.82rem;margin-bottom:0.2rem;">
                                <span>
                                    <span style="color:var(--text-secondary);margin-right:0.3rem;">#${rank}</span>
                                    <span style="font-weight:700;">${s.name}</span>
                                    <span style="color:var(--text-secondary);font-size:0.75rem;margin-left:0.3rem;">(${s.code})</span>
                                </span>
                                <span style="color:var(--profit-color);font-weight:600;">${s.score}</span>
                            </div>
                            <div style="height:4px;background:rgba(255,255,255,0.08);border-radius:3px;overflow:hidden;margin-bottom:0.15rem;">
                                <div style="height:100%;width:${barW}%;background:linear-gradient(90deg,#3b82f6,#10b981);border-radius:3px;"></div>
                            </div>
                            <div style="font-size:0.72rem;color:var(--text-secondary);">${themeStr}</div>
                        </div>`;
                    }).join('');

                // 테마 키워드 태그
                const maxTheme = res.top_themes.length > 0 ? res.top_themes[0].count : 1;
                document.getElementById('watchlist-themes').innerHTML = res.top_themes.length === 0
                    ? '<div style="color:var(--text-secondary);font-size:0.85rem;">감지된 테마 없음</div>'
                    : res.top_themes.map(t => {
                        const intensity = Math.max(0.3, t.count / maxTheme);
                        const size = 0.75 + intensity * 0.35;
                        return `<span style="padding:0.2rem 0.6rem; border-radius:20px; font-size:${size.toFixed(2)}rem;
                            background:rgba(59,130,246,${(intensity * 0.25).toFixed(2)});
                            border:1px solid rgba(59,130,246,${(intensity * 0.5).toFixed(2)});
                            color:rgba(255,255,255,${(0.5 + intensity * 0.5).toFixed(2)});">
                            ${t.name} <span style="font-size:0.7rem;opacity:0.7;">${t.count}</span>
                        </span>`;
                    }).join('');

                // 채널 가중치
                const weights = Object.entries(res.channel_weights || {});
                document.getElementById('watchlist-weights').innerHTML = weights.length === 0
                    ? '<span style="color:var(--text-secondary);font-size:0.8rem;">데이터 없음</span>'
                    : weights.map(([ch, w]) => {
                        const col = w >= 1.0 ? 'var(--profit-color)' : (w < 0.8 ? 'var(--loss-color)' : 'var(--text-secondary)');
                        return `<div style="display:flex; justify-content:space-between; font-size:0.8rem;">
                            <span style="color:var(--text-secondary);">${ch}</span>
                            <span style="font-weight:600; color:${col};">×${w.toFixed(3)}</span>
                        </div>`;
                    }).join('');
            })
            .catch(err => console.error('Watchlist report fetch error:', err));
    }

    // Collection Stats
    function updateCollectionStats() {
        fetch('/api/collection-stats')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                document.getElementById('collection-channels').textContent =
                    `텔레그램 ${res.tracked_channels}개 채널 추적 중`;

                // 네이버 리서치
                const naverEl = document.getElementById('naver-stats-grid');
                const naverEntries = Object.entries(res.naver || {});
                if (naverEntries.length === 0) {
                    naverEl.innerHTML = '<div class="collection-item" style="grid-column:1/-1;color:var(--text-secondary)">데이터 없음</div>';
                } else {
                    naverEl.innerHTML = naverEntries.map(([, v]) => `
                        <div class="collection-item">
                            <div class="ci-label">${v.label}</div>
                            <div class="ci-count">${v.count.toLocaleString()}건</div>
                            <div class="ci-time">${v.latest || '-'}</div>
                        </div>
                    `).join('');
                }

                // 텔레그램 텍스트
                const tgEl = document.getElementById('telegram-stats-grid');
                const tgEntries = Object.entries(res.telegram || {});
                if (tgEntries.length === 0) {
                    tgEl.innerHTML = '<div class="collection-item" style="grid-column:1/-1;color:var(--text-secondary)">데이터 없음</div>';
                } else {
                    tgEl.innerHTML = tgEntries.map(([name, v]) => `
                        <div class="collection-item">
                            <div class="ci-label">${name}</div>
                            <div class="ci-count">${v.count.toLocaleString()}건</div>
                            <div class="ci-time">${v.latest || '-'}</div>
                        </div>
                    `).join('');
                }
            })
            .catch(err => console.error('Collection stats fetch error:', err));
    }

    // 거래 성과 (closed_positions.json 기반, KIS API 호출 없음)
    function _fmtPnl(amt) {
        const sign = amt >= 0 ? '+' : '';
        return `${sign}₩ ${Math.round(amt).toLocaleString()}`;
    }
    function _fmtRate(rate) {
        if (rate === null || rate === undefined) return '-';
        const sign = rate >= 0 ? '+' : '';
        return `${sign}${Number(rate).toFixed(2)}%`;
    }
    function _rateColor(rate) {
        if (rate > 0) return 'var(--profit-color)';
        if (rate < 0) return 'var(--loss-color)';
        return 'var(--text-secondary)';
    }

    function updatePerformance() {
        const qs = _selectedAccount ? `?account_no=${encodeURIComponent(_selectedAccount)}` : '';

        // 1) 요약 KPI
        fetch('/api/performance' + qs)
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                const d = res.data || {};
                const setText = (id, val, color) => {
                    const el = document.getElementById(id);
                    if (!el) return;
                    el.textContent = val;
                    if (color) el.style.color = color;
                };
                setText('perf-trade-count', `${(d.trade_count || 0).toLocaleString()}회`);
                setText('perf-win-rate',
                    d.trade_count ? `${d.win_rate.toFixed(1)}% (${d.win_count}/${d.trade_count})` : '-',
                    d.trade_count && d.win_rate >= 50 ? 'var(--profit-color)' : 'var(--loss-color)');
                setText('perf-total-pnl',
                    d.trade_count ? _fmtPnl(d.total_pnl_amt) : '-',
                    _rateColor(d.total_pnl_amt || 0));
                setText('perf-avg-rate',
                    d.trade_count ? _fmtRate(d.avg_pnl_rate) : '-',
                    _rateColor(d.avg_pnl_rate || 0));
                setText('perf-best-rate',
                    d.trade_count ? _fmtRate(d.best_pnl_rate) : '-',
                    'var(--profit-color)');
                setText('perf-worst-rate',
                    d.trade_count ? _fmtRate(d.worst_pnl_rate) : '-',
                    'var(--loss-color)');

                const meta = document.getElementById('performance-meta');
                if (meta) {
                    meta.textContent = d.trade_count
                        ? `총 ${d.trade_count.toLocaleString()}건 누적 (closed_positions.json 기반)`
                        : '매도 이력 없음 — closed_positions.json 비어있음';
                }
            })
            .catch(err => console.error('Performance fetch error:', err));

        // 2) 종목별 랭킹 (상위 5)
        fetch('/api/performance/by-stock' + qs)
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                const body = document.getElementById('performance-by-stock-body');
                if (!body) return;
                const rows = (res.data || []).slice(0, 5);
                if (rows.length === 0) {
                    body.innerHTML = `<tr><td colspan="5" class="text-center" style="color:var(--text-secondary)">매도 이력 없음</td></tr>`;
                    return;
                }
                body.innerHTML = rows.map((r, i) => `
                    <tr>
                        <td style="color:var(--text-secondary)">#${i + 1}</td>
                        <td><span style="font-weight:600">${r.stock_name || r.stock_code}</span>
                            <span style="color:var(--text-secondary);font-size:0.78rem;"> (${r.stock_code})</span></td>
                        <td>${r.trade_count.toLocaleString()}회</td>
                        <td style="color:${_rateColor(r.avg_pnl_rate)};font-weight:600">${_fmtRate(r.avg_pnl_rate)}</td>
                        <td style="color:${_rateColor(r.total_pnl_amt)};font-weight:600">${_fmtPnl(r.total_pnl_amt)}</td>
                    </tr>
                `).join('');
            })
            .catch(err => console.error('Performance by-stock fetch error:', err));
    }

    // 포지션 편집 모달 (손절/익절 + 매수일)
    window.openEditModal = function(posKey, stopLoss, takeProfit, buyDate, label) {
        document.getElementById('edit-pos-key').value = posKey;
        document.getElementById('edit-stop-loss').value = stopLoss;
        document.getElementById('edit-take-profit').value = takeProfit;
        document.getElementById('edit-buy-date').value = buyDate || '';
        document.getElementById('edit-pos-label').textContent = label || posKey;
        document.getElementById('edit-modal').style.display = 'flex';
    };

    window.closeEditModal = function() {
        document.getElementById('edit-modal').style.display = 'none';
    };

    window.submitEditModal = function() {
        const key     = document.getElementById('edit-pos-key').value;
        const sl      = parseFloat(document.getElementById('edit-stop-loss').value);
        const tp      = parseFloat(document.getElementById('edit-take-profit').value);
        const buyDate = document.getElementById('edit-buy-date').value;
        if (!sl || !tp || sl <= 0 || tp <= 0) { alert('유효한 값을 입력하세요.'); return; }
        fetch(`/api/positions/${key}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ stop_loss: sl, take_profit: tp, buy_date: buyDate }),
        })
        .then(r => r.json())
        .then(r => {
            if (r.success) { closeEditModal(); updatePositions(); }
            else alert('저장 실패: ' + (r.error || '알 수 없는 오류'));
        })
        .catch(() => alert('서버 오류'));
    };

    // Initialize
    updateSystemStatus();
    updateAiCosts();
    updateBalance();
    updatePositions();
    updateLogs();
    updateCollectionStats();
    updateWatchlistReport();
    updatePerformance();

    // Polling
    setInterval(updateSystemStatus, 30000);
    setInterval(() => { updateBalance(); updatePositions(); }, FAST_POLL_MS);
    setInterval(updateLogs, SLOW_POLL_MS);
    setInterval(updateCollectionStats, 60000);
    setInterval(updateWatchlistReport, 300000); // 5분마다 갱신
    setInterval(updatePerformance, 30000); // 거래 성과 — 30초마다 갱신 (히스토리 기반이라 느린 polling)

    refreshLogsBtn.addEventListener('click', () => {
        updateLogs();
        refreshLogsBtn.style.transform = 'rotate(180deg)';
        setTimeout(() => refreshLogsBtn.style.transform = 'rotate(0deg)', 300);
    });
});
