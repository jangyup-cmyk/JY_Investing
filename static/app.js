document.addEventListener('DOMContentLoaded', () => {
    const FAST_POLL_MS = 5000;
    const SLOW_POLL_MS = 10000;

    const configContainer = document.getElementById('config-container');
    const balanceContainer = document.getElementById('balance-container');
    const positionsBody = document.getElementById('positions-body');
    const logContainer = document.getElementById('log-container');
    const refreshLogsBtn = document.getElementById('refresh-logs-btn');

    // System Status
    function updateSystemStatus() {
        fetch('/api/system-status')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                document.getElementById('scheduler-status').textContent = res.scheduler_running ? '✅ 가동 중' : '⚠️ 중지됨';
                document.getElementById('scheduler-status').style.color = res.scheduler_running ? 'var(--profit-color)' : 'var(--warn-color)';
                document.getElementById('tg-status').textContent = res.telegram_monitor ? '✅ 활성' : '⏸ 비활성';
                document.getElementById('naver-status').textContent = res.naver_research ? '✅ 활성' : '⏸ 비활성';
                document.getElementById('server-time').textContent = res.server_time;
            })
            .catch(err => console.error('System status fetch error:', err));
    }

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

    // Balance
    function updateBalance() {
        fetch('/api/balance')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                balanceContainer.innerHTML = '';
                res.data.forEach(b => {
                    if (b.error) {
                        balanceContainer.innerHTML += `
                            <div class="glass-card metric-card">
                                <h3>${b.name} (${b.account})</h3>
                                <div class="value" style="color: var(--loss-color)">API 오류</div>
                                <div class="sub-value">${b.error}</div>
                            </div>
                        `;
                        return;
                    }
                    const totalEval = b.total_eval_amount || 0;
                    const totalBuy  = b.total_buy_amount  || 0;
                    const pnl       = totalEval - totalBuy;
                    const pnlRate   = totalBuy > 0 ? (pnl / totalBuy) * 100 : 0;
                    const pnlColor  = pnl > 0 ? 'var(--profit-color)' : (pnl < 0 ? 'var(--loss-color)' : 'var(--text-primary)');
                    balanceContainer.innerHTML += `
                        <div class="glass-card metric-card">
                            <h3>${b.name} 계좌 자산</h3>
                            <div class="value">₩ ${totalEval.toLocaleString()}</div>
                            <div class="sub-value">주문가능 현금: ₩ ${(b.available_balance || 0).toLocaleString()} | 보유 종목 ${b.holdings_count || 0}개</div>
                            <div class="sub-value" style="margin-top:10px; color: ${pnlColor}">
                                평가 손익: ₩ ${pnl.toLocaleString()} (${pnlRate > 0 ? '+' : ''}${pnlRate.toFixed(2)}%)
                            </div>
                        </div>
                    `;
                });
            })
            .catch(err => console.error('Balance fetch error:', err));
    }

    // Positions
    function updatePositions() {
        fetch('/api/positions')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                if (res.data.length === 0) {
                    positionsBody.innerHTML = `<tr><td colspan="7" class="text-center" style="color: var(--text-secondary)">현재 보유 중인 포지션이 없습니다.</td></tr>`;
                    return;
                }
                positionsBody.innerHTML = res.data.map(pos => `
                    <tr>
                        <td>${pos.account_no}</td>
                        <td style="font-weight:600">${pos.stock_name} <span style="color:var(--text-secondary);font-size:0.8rem">(${pos.stock_code})</span></td>
                        <td>₩ ${Number(pos.buy_price).toLocaleString()}</td>
                        <td>${pos.qty.toLocaleString()} 주</td>
                        <td style="color: var(--loss-color)">₩ ${Number(pos.stop_loss).toLocaleString()}</td>
                        <td style="color: var(--profit-color)">₩ ${Number(pos.take_profit).toLocaleString()}</td>
                        <td style="font-size:0.8rem; color:var(--text-secondary)">${new Date(pos.opened_at).toLocaleString()}</td>
                    </tr>
                `).join('');
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

    // Initialize
    updateSystemStatus();
    updateAiCosts();
    updateBalance();
    updatePositions();
    updateLogs();

    // Polling
    setInterval(updateSystemStatus, 30000);
    setInterval(() => { updateBalance(); updatePositions(); }, FAST_POLL_MS);
    setInterval(updateLogs, SLOW_POLL_MS);

    refreshLogsBtn.addEventListener('click', () => {
        updateLogs();
        refreshLogsBtn.style.transform = 'rotate(180deg)';
        setTimeout(() => refreshLogsBtn.style.transform = 'rotate(0deg)', 300);
    });
});
