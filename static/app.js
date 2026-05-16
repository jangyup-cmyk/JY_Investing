document.addEventListener('DOMContentLoaded', () => {
    // API Polling Intervals
    const FAST_POLL_MS = 5000;   // 5초 (잔고, 포지션)
    const SLOW_POLL_MS = 10000;  // 10초 (로그)

    // Elements
    const configContainer = document.getElementById('config-container');
    const balanceContainer = document.getElementById('balance-container');
    const positionsBody = document.getElementById('positions-body');
    const logContainer = document.getElementById('log-container');
    const refreshLogsBtn = document.getElementById('refresh-logs-btn');

    // Fetch Config once
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

    // Fetch Balance
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
                    const totalBuy = b.total_buy_amount || 0;
                    const pnl = totalEval - totalBuy;
                    const pnlRate = totalBuy > 0 ? (pnl / totalBuy) * 100 : 0;
                    const pnlColor = pnl > 0 ? 'var(--profit-color)' : (pnl < 0 ? 'var(--loss-color)' : 'var(--text-primary)');

                    balanceContainer.innerHTML += `
                        <div class="glass-card metric-card">
                            <h3>${b.name} 계좌 자산</h3>
                            <div class="value">₩ ${b.total_balance.toLocaleString()}</div>
                            <div class="sub-value">주문가능 현금: ₩ ${b.available_balance.toLocaleString()}</div>
                            <div class="sub-value" style="margin-top:10px; color: ${pnlColor}">
                                평가 손익: ₩ ${pnl.toLocaleString()} (${pnlRate > 0 ? '+' : ''}${pnlRate.toFixed(2)}%)
                            </div>
                        </div>
                    `;
                });
            })
            .catch(err => console.error('Balance fetch error:', err));
    }

    // Fetch Positions
    function updatePositions() {
        fetch('/api/positions')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                
                if (res.data.length === 0) {
                    positionsBody.innerHTML = `<tr><td colspan="7" class="text-center" style="color: var(--text-secondary)">현재 보유 중인 포지션이 없습니다.</td></tr>`;
                    return;
                }

                positionsBody.innerHTML = '';
                res.data.forEach(pos => {
                    const buyDate = new Date(pos.opened_at).toLocaleString();
                    positionsBody.innerHTML += `
                        <tr>
                            <td>${pos.account_no}</td>
                            <td style="font-weight: 600">${pos.stock_name} <span style="color:var(--text-secondary);font-size:0.8rem">(${pos.stock_code})</span></td>
                            <td>₩ ${pos.buy_price.toLocaleString()}</td>
                            <td>${pos.qty.toLocaleString()} 주</td>
                            <td style="color: var(--loss-color)">₩ ${pos.stop_loss.toLocaleString()}</td>
                            <td style="color: var(--profit-color)">₩ ${pos.take_profit.toLocaleString()}</td>
                            <td style="font-size: 0.8rem; color: var(--text-secondary)">${buyDate}</td>
                        </tr>
                    `;
                });
            })
            .catch(err => console.error('Positions fetch error:', err));
    }

    // Fetch Logs
    function updateLogs() {
        fetch('/api/logs')
            .then(res => res.json())
            .then(res => {
                if (!res.success) return;
                
                if (res.data.length === 0) {
                    logContainer.innerHTML = `<div class="log-entry">표시할 로그가 없습니다.</div>`;
                    return;
                }

                logContainer.innerHTML = '';
                res.data.forEach(log => {
                    const isError = log.level === 'ERROR';
                    const isWarning = log.level === 'WARNING';
                    
                    let levelClass = 'INFO';
                    if (isError) levelClass = 'ERROR';
                    if (isWarning) levelClass = 'WARNING';

                    logContainer.innerHTML += `
                        <div class="log-entry">
                            <div class="log-time">${log.timestamp || '-'}</div>
                            <div class="log-level ${levelClass}">[${log.level}]</div>
                            <div class="log-msg">
                                <span style="color:var(--text-secondary)">[${log.module}]</span> 
                                ${log.message}
                            </div>
                        </div>
                    `;
                });
            })
            .catch(err => console.error('Logs fetch error:', err));
    }

    // Initialize
    updateBalance();
    updatePositions();
    updateLogs();

    // Start Polling
    setInterval(() => {
        updateBalance();
        updatePositions();
    }, FAST_POLL_MS);

    setInterval(updateLogs, SLOW_POLL_MS);

    // Manual Refresh Logs
    refreshLogsBtn.addEventListener('click', () => {
        updateLogs();
        refreshLogsBtn.style.transform = 'rotate(180deg)';
        setTimeout(() => refreshLogsBtn.style.transform = 'rotate(0deg)', 300);
    });
});
