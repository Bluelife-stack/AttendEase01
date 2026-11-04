(() => {
  const root = document.getElementById('attendanceTrend');
  const metricSelect = document.getElementById('trendMetric');
  const rangeSelect = document.getElementById('trendRange');
  if (!root || !metricSelect || !rangeSelect) return;
  let rows = [];
  try { rows = JSON.parse(root.dataset.series || '[]'); } catch (_) { rows = []; }
  const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const label = month => { const [y,m] = month.split('-').map(Number); return new Date(y,m-1,1).toLocaleDateString(undefined,{month:'short',year:'2-digit'}); };
  function render() {
    const range = rangeSelect.value;
    const data = range === 'all' ? rows : rows.slice(-Number(range));
    if (!data.length) { root.innerHTML = '<div class="trend-empty">No attendance data is available for this period.</div>'; return; }
    const metric = metricSelect.value;
    const values = data.map(r => metric === 'attendance' ? Number(r.attendance_percentage || 0) : metric === 'absenteeism' ? Number(r.absenteeism_rate || 0) : Number(r.present_count || 0));
    const maxValue = Math.max(100, ...values) || 100;
    const minValue = metric === 'present' ? 0 : 0;
    const w = Math.max(520, data.length * 86), h = 230, left = 42, right = 18, top = 18, bottom = 38;
    const plotW = w-left-right, plotH = h-top-bottom;
    const x = i => left + (data.length === 1 ? plotW/2 : i*plotW/(data.length-1));
    const y = v => top + plotH - ((v-minValue)/(maxValue-minValue || 1))*plotH;
    const points = values.map((v,i)=>`${x(i)},${y(v)}`).join(' ');
    const area = `${left},${top+plotH} ${points} ${x(data.length-1)},${top+plotH}`;
    const ticks = metric === 'present' ? [0,Math.round(maxValue/2),maxValue] : [0,50,100];
    let grid = '';
    ticks.forEach(t=>{grid += `<line x1="${left}" y1="${y(t)}" x2="${w-right}" y2="${y(t)}" class="trend-gridline"/><text x="${left-10}" y="${y(t)+4}" text-anchor="end" class="trend-axis">${Math.round(t)}${metric==='present'?'':'%'}</text>`;});
    let marks = '';
    data.forEach((r,i)=>{const val=values[i], title=`${label(r.month)} · ${metric==='present'?'Present records':metric==='attendance'?'Attendance rate':'Absenteeism rate'}: ${val}${metric==='present'?'':'%'}`;marks+=`<circle class="trend-point" cx="${x(i)}" cy="${y(val)}" r="5" tabindex="0" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title></circle><text x="${x(i)}" y="${h-12}" text-anchor="middle" class="trend-axis">${esc(label(r.month))}</text>`;});
    root.innerHTML = `<div class="trend-svg-wrap"><svg viewBox="0 0 ${w} ${h}" role="img" aria-label="Interactive monthly attendance trend">${grid}<polygon points="${area}" class="trend-area"/><polyline points="${points}" class="trend-line"/>${marks}</svg></div>`;
  }
  metricSelect.addEventListener('change', render); rangeSelect.addEventListener('change', render); render();
})();
