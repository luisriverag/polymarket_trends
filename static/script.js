function initCharts(volumeData, closedStats) {
    const volumeCtx = document.getElementById('volumeChart').getContext('2d');
    const resolutionCtx = document.getElementById('resolutionChart').getContext('2d');
    
    const labels = volumeData.map(d => {
        const date = new Date(d.date);
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    });
    
    const volumes = volumeData.map(d => d.volume);
    
    new Chart(volumeCtx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Volume ($)',
                data: volumes,
                backgroundColor: volumes.map((v, i) => {
                    const max = Math.max(...volumes);
                    const alpha = 0.3 + (v / max) * 0.7;
                    return `rgba(88, 166, 255, ${alpha})`;
                }),
                borderColor: '#58a6ff',
                borderWidth: 1,
                borderRadius: 4,
                borderSkipped: false,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: '#161b22',
                    titleColor: '#c9d1d9',
                    bodyColor: '#c9d1d9',
                    borderColor: '#30363d',
                    borderWidth: 1,
                    padding: 12,
                    displayColors: false,
                    callbacks: {
                        label: function(context) {
                            const value = context.raw;
                            if (value >= 1e6) {
                                return '$' + (value / 1e6).toFixed(2) + 'M';
                            } else if (value >= 1e3) {
                                return '$' + (value / 1e3).toFixed(2) + 'K';
                            }
                            return '$' + value.toFixed(2);
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        color: '#30363d',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#8b949e',
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 10
                        },
                        maxRotation: 45,
                        minRotation: 45
                    }
                },
                y: {
                    grid: {
                        color: '#30363d',
                        drawBorder: false
                    },
                    ticks: {
                        color: '#8b949e',
                        font: {
                            family: "'JetBrains Mono', monospace",
                            size: 10
                        },
                        callback: function(value) {
                            if (value >= 1e6) {
                                return '$' + (value / 1e6).toFixed(1) + 'M';
                            } else if (value >= 1e3) {
                                return '$' + (value / 1e3).toFixed(0) + 'K';
                            }
                            return '$' + value;
                        }
                    }
                }
            }
        }
    });
    
    const yesCount = closedStats.yes_resolved || 0;
    const noCount = closedStats.no_resolved || 0;
    
    if (yesCount > 0 || noCount > 0) {
        new Chart(resolutionCtx, {
            type: 'doughnut',
            data: {
                labels: ['Yes', 'No'],
                datasets: [{
                    data: [yesCount, noCount],
                    backgroundColor: ['#3fb950', '#f85149'],
                    borderColor: '#161b22',
                    borderWidth: 3,
                    hoverOffset: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            color: '#c9d1d9',
                            font: {
                                family: "'JetBrains Mono', monospace",
                                size: 11
                            },
                            padding: 16,
                            usePointStyle: true,
                            pointStyle: 'circle'
                        }
                    },
                    tooltip: {
                        backgroundColor: '#161b22',
                        titleColor: '#c9d1d9',
                        bodyColor: '#c9d1d9',
                        borderColor: '#30363d',
                        borderWidth: 1,
                        padding: 12
                    }
                }
            }
        });
    } else {
        document.getElementById('resolutionChart').parentElement.innerHTML = 
            '<div class="empty-state"><p>No resolution data available</p></div>';
    }
}

function logLoading(msg, type = 'info') {
    const log = document.getElementById('loading-log');
    if (!log) return;
    const time = new Date().toLocaleTimeString('en-US', {hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit'});
    const entry = document.createElement('div');
    entry.className = 'log-entry';
    entry.innerHTML = `<span class="log-time">[${time}]</span><span class="log-${type}">${msg}</span>`;
    log.appendChild(entry);
    log.scrollTop = log.scrollHeight;
}

async function refreshData() {
    const btn = document.getElementById('refresh-btn');
    const log = document.getElementById('loading-log');
    if (log) log.innerHTML = '';
    logLoading('Starting refresh...', 'info');
    btn.textContent = '⟳ Refreshing...';
    btn.disabled = true;
    
    try {
        const resp = await fetch('/api/refresh');
        const data = await resp.json();
        
        const dbSize = data.db_size || 0;
        const sizeMB = (dbSize / 1024 / 1024).toFixed(2);
        logLoading(`DB: ${sizeMB} MB`, 'info');
        
        logLoading('Fetching markets...', 'info');
        await new Promise(r => setTimeout(r, 2000));
        logLoading('Markets ✓', 'ok');
        
        logLoading('Fetching events...', 'info');
        await new Promise(r => setTimeout(r, 1000));
        logLoading('Events ✓', 'ok');
        
        logLoading('Fetching leaderboard...', 'info');
        await new Promise(r => setTimeout(r, 1000));
        logLoading('Leaderboard ✓', 'ok');
        
        logLoading('Analyzing...', 'info');
        await new Promise(r => setTimeout(r, 1000));
        logLoading('Done ✓', 'ok');
        
        location.reload();
    } catch (e) {
        console.error('Refresh failed:', e);
        logLoading('Error: ' + e.message, 'err');
        btn.textContent = '↻ Refresh';
        btn.disabled = false;
    }
}

document.addEventListener('DOMContentLoaded', function() {
    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', refreshData);
    }
});

function initDistributionChart(distribution) {
    const ctx = document.getElementById('distributionChart');
    if (!ctx) return;
    
    const ctx2d = ctx.getContext('2d');
    const labels = Object.keys(distribution);
    const data = Object.values(distribution);
    
    new Chart(ctx2d, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Markets',
                data: data,
                backgroundColor: data.map((v, i) => {
                    const hue = (i / 10) * 120;
                    return `hsla(${hue}, 70%, 50%, 0.7)`;
                }),
                borderColor: '#30363d',
                borderWidth: 1,
                borderRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#161b22',
                    titleColor: '#c9d1d9',
                    bodyColor: '#c9d1d9',
                    borderColor: '#30363d',
                    borderWidth: 1
                }
            },
            scales: {
                x: {
                    grid: { color: '#30363d', drawBorder: false },
                    ticks: { color: '#8b949e', font: { size: 10 } }
                },
                y: {
                    grid: { color: '#30363d', drawBorder: false },
                    ticks: { color: '#8b949e', font: { size: 10 } }
                }
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    const tabs = document.querySelectorAll('.resolution-tab');
    tabs.forEach(tab => {
        tab.addEventListener('click', function() {
            tabs.forEach(t => t.classList.remove('active'));
            this.classList.add('active');
            
            const tabId = this.getAttribute('data-tab');
            document.querySelectorAll('.resolution-list').forEach(list => {
                list.classList.remove('active');
            });
            document.getElementById('tab-' + tabId).classList.add('active');
        });
    });
});
