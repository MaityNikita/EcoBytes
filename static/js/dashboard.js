document.addEventListener('DOMContentLoaded', async () => {
  const loading = document.getElementById('loading');
  const content = document.getElementById('dashboard-content');
  
  try {
    // Determine if we need to fetch demo data based on URL or attempt real api
    const isDemo = window.location.pathname.includes('/api/demo') || new URLSearchParams(window.location.search).has('demo');
    const endpoint = isDemo ? '/api/demo' : '/api/footprint';
    
    const res = await fetch(endpoint);
    
    if (!res.ok) {
      if (res.status === 401) {
        window.location.href = '/login';
        return;
      }
      throw new Error('Failed to fetch footprint data');
    }
    
    const data = await res.json();
    populateDashboard(data);
    
    // Smooth reveal
    loading.classList.add('hidden');
    content.classList.remove('hidden');
    
    // Trigger animations
    setTimeout(animateBars, 100);
    
  } catch (err) {
    console.error(err);
    loading.innerHTML = `<p style="color: #ff6b6b;">Error: ${err.message}. <br> Try reloading or reconnecting your account.</p>`;
  }
});

function populateDashboard(data) {
  // Score
  const score = data.score;
  document.getElementById('score-grade').textContent = score.grade;
  document.getElementById('score-grade').style.color = score.color;
  document.getElementById('score-circle').style.borderColor = score.color;
  document.getElementById('score-value').textContent = score.score;
  document.getElementById('score-label').textContent = score.label;
  document.getElementById('score-label').style.color = score.color;

  // Emissions
  document.getElementById('total-kg').textContent = data.footprint.grand_total_kg.toFixed(1);
  document.getElementById('yearly-kg').textContent = data.footprint.grand_total_kg_year.toFixed(1);

  // Sources
  const raw = data.raw_usage;
  document.getElementById('gmail-msgs').textContent = (raw.gmail.total_messages || 0).toLocaleString();
  document.getElementById('drive-gb').textContent = (raw.drive.total_storage_gb || 0).toFixed(1);

  // Breakdown Chart
  renderBreakdown(data.footprint);

  // Goal
  if (data.goal) {
    renderGoal(data.goal);
  }

  // Recommendations
  renderRecommendations(data.recommendations);
  
  // History Chart
  if (data.history && data.history.length > 0) {
    renderHistory(data.history);
  }
  
  // Peers
  if (data.peers) {
    renderPeers(data.peers, data.footprint.grand_total_kg);
  }
  
  // Offset setup
  setupOffset(data.footprint.grand_total_kg);
}

// Global baseline for goal setting
let currentBaselineKg = 0;

function renderGoal(goal) {
  const container = document.getElementById('goal-container');
  if (!goal) return;
  
  const pct = goal.progress_pct || 0;
  
  container.innerHTML = `
    <div style="margin-bottom: 0.5rem; display: flex; justify-content: space-between; font-size: 0.9rem;">
      <span>Target: <strong>${goal.target_kg} kg/mo</strong> (-${goal.target_pct}%)</span>
      <span style="color: var(--green-accent); font-family: monospace;">${pct.toFixed(1)}% achieved</span>
    </div>
    <div class="bar-track" style="height: 12px; background: rgba(255,255,255,0.1);">
      <div class="bar-fill" style="width: ${pct}%; background: var(--green-accent); height: 100%; border-radius: 4px; transition: width 1s;"></div>
    </div>
  `;
}

document.addEventListener('DOMContentLoaded', () => {
  const saveBtn = document.getElementById('save-goal-btn');
  if (saveBtn) {
    saveBtn.addEventListener('click', async () => {
      const pct = document.getElementById('goal-pct').value;
      const baseline = parseFloat(document.getElementById('total-kg').textContent) || 50;
      
      saveBtn.textContent = 'Saving...';
      
      try {
        await fetch('/api/goals', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ target_pct: parseInt(pct), baseline_kg: baseline })
        });
        
        window.location.reload();
      } catch (err) {
        console.error(err);
        saveBtn.textContent = 'Error';
      }
    });
  }
});

function renderBreakdown(fp) {
  const container = document.getElementById('breakdown-bars');
  container.innerHTML = '';
  
  const categories = [
    { label: 'Device Usage', val: fp.devices_total || 0, color: '#6FCF97' },
    { label: 'Streaming', val: fp.streaming.total || 0, color: '#F2C94C' },
    { label: 'Cloud Storage', val: fp.storage.total || 0, color: '#4285F4' },
    { label: 'Email', val: fp.email.total || 0, color: '#EA4335' },
    { label: 'Web & AI', val: fp.web.total || 0, color: '#9B51E0' }
  ];
  
  // Sort by highest
  categories.sort((a, b) => b.val - a.val);
  
  const maxVal = categories[0].val || 1; // avoid div by 0
  
  categories.forEach(cat => {
    if (cat.val === 0) return;
    
    const pct = Math.min(100, Math.max(2, (cat.val / maxVal) * 100)); // min 2% for visibility
    const kg = (cat.val / 1000).toFixed(2);
    
    const html = `
      <div class="bar-row">
        <div class="bar-header">
          <span class="bar-label">${cat.label}</span>
          <span class="bar-value">${kg} kg</span>
        </div>
        <div class="bar-track">
          <div class="bar-fill" data-width="${pct}%" style="background-color: ${cat.color}"></div>
        </div>
      </div>
    `;
    container.insertAdjacentHTML('beforeend', html);
  });
}

function animateBars() {
  const fills = document.querySelectorAll('.bar-fill');
  fills.forEach(fill => {
    fill.style.width = fill.getAttribute('data-width');
  });
}

function renderRecommendations(recs) {
  const container = document.getElementById('recs-list');
  container.innerHTML = '';
  
  if (!recs || recs.length === 0) {
    container.innerHTML = '<p style="color: var(--text-muted); font-size: 0.9rem;">Great job! Your footprint is highly optimized.</p>';
    return;
  }
  
  recs.forEach(rec => {
    const html = `
      <div class="rec-item">
        <div class="rec-header">
          <span class="rec-title">${rec.title}</span>
          <span class="rec-impact">-${(rec.saving_g_month / 1000).toFixed(2)} kg/mo</span>
        </div>
        <p class="rec-detail">${rec.detail}</p>
      </div>
    `;
    container.insertAdjacentHTML('beforeend', html);
  });
}

function renderHistory(history) {
  const ctx = document.getElementById('historyChart').getContext('2d');
  
  const labels = history.map(h => h.date);
  const data = history.map(h => h.kg);
  
  new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Emissions (kg CO₂e)',
        data: data,
        borderColor: '#6FCF97',
        backgroundColor: 'rgba(111, 207, 151, 0.1)',
        borderWidth: 2,
        fill: true,
        tension: 0.4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }
      },
      scales: {
        y: {
          beginAtZero: true,
          grid: { color: 'rgba(255,255,255,0.05)' },
          ticks: { color: 'rgba(245,245,240,0.6)' }
        },
        x: {
          grid: { display: false },
          ticks: { color: 'rgba(245,245,240,0.6)' }
        }
      }
    }
  });
}

function renderPeers(peers, myKg) {
  document.getElementById('peer-label').textContent = `vs ${peers.label}`;
  
  const diff = myKg - peers.avg_kg_month;
  const pct = Math.round(Math.abs(diff) / peers.avg_kg_month * 100);
  
  const statEl = document.getElementById('peer-stat');
  const msgEl = document.getElementById('peer-message');
  
  if (diff <= 0) {
    statEl.textContent = `-${pct}%`;
    statEl.style.color = '#6FCF97';
    msgEl.textContent = "You emit less than the average!";
    msgEl.style.color = '#6FCF97';
  } else {
    statEl.textContent = `+${pct}%`;
    statEl.style.color = '#ff6b6b';
    msgEl.textContent = "You emit more than the average.";
    msgEl.style.color = '#ff6b6b';
  }
}

function setupOffset(kg) {
  const costPerTonne = 15.00;
  const cost = (kg / 1000) * costPerTonne;
  
  document.getElementById('offset-kg').textContent = `${kg.toFixed(1)} kg`;
  document.getElementById('offset-price').textContent = `$${cost.toFixed(2)}`;
}

function openOffsetModal() {
  document.getElementById('offset-modal').classList.remove('hidden');
}
