(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var danger = style.getPropertyValue('--danger').trim();
  var warning = style.getPropertyValue('--warning').trim();
  var success = style.getPropertyValue('--success').trim();

  // --- Chart: Issue Severity ---
  var chart1 = echarts.init(document.getElementById('chart-severity'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: { trigger: 'item', appendToBody: true },
    legend: {
      orient: 'vertical',
      right: '10%',
      top: 'center',
      textStyle: { color: ink, fontSize: 13 },
      itemWidth: 12,
      itemHeight: 12
    },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['35%', '50%'],
      avoidLabelOverlap: false,
      label: {
        show: true,
        position: 'outside',
        formatter: '{b}\n{d}%',
        color: ink,
        fontSize: 12
      },
      labelLine: { lineStyle: { color: rule } },
      itemStyle: { borderColor: bg2, borderWidth: 2 },
      data: [
        { value: 7, name: '严重Bug', itemStyle: { color: danger } },
        { value: 9, name: 'Schema不一致', itemStyle: { color: warning } },
        { value: 8, name: '功能缺失', itemStyle: { color: accent2 } },
        { value: 6, name: '优化建议', itemStyle: { color: success } }
      ]
    }]
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // --- Chart: Schema Consistency ---
  var chart2 = echarts.init(document.getElementById('chart-schema'), null, { renderer: 'svg' });
  chart2.setOption({
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      appendToBody: true
    },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
      type: 'value',
      max: 100,
      axisLabel: { formatter: '{value}%', color: muted, fontSize: 11 },
      splitLine: { lineStyle: { color: rule } },
      axisLine: { lineStyle: { color: rule } }
    },
    yAxis: {
      type: 'category',
      data: [
        'GenSkill', 'ArmySkill', 'ArmyGroupSkill', 'SFMagic', 'GenLV',
        'Age', 'Variable', 'DefSkill', 'ItemEnhance', 'Thing',
        'Nation', 'History', 'Title',
        'General01', 'Soldier',
        'BFMagic', 'Dialogue', 'BuildingPos',
        'SuperAtk', 'BFFront', 'Format', 'ChessFormat', 'font', 'City'
      ],
      axisLabel: { color: ink, fontSize: 11, fontFamily: "'GeistMono','Consolas',monospace" },
      axisLine: { lineStyle: { color: rule } },
      inverse: true
    },
    series: [{
      type: 'bar',
      data: [
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 100, itemStyle: { color: success } },
        { value: 90, itemStyle: { color: accent2 } },
        { value: 85, itemStyle: { color: accent2 } },
        { value: 80, itemStyle: { color: warning } },
        { value: 40, itemStyle: { color: warning } },
        { value: 50, itemStyle: { color: warning } },
        { value: 20, itemStyle: { color: danger } },
        { value: 15, itemStyle: { color: danger } },
        { value: 15, itemStyle: { color: danger } },
        { value: 5, itemStyle: { color: danger } },
        { value: 10, itemStyle: { color: danger } },
        { value: 15, itemStyle: { color: danger } }
      ],
      barWidth: 16,
      label: {
        show: true,
        position: 'right',
        formatter: '{c}%',
        color: muted,
        fontSize: 11
      },
      markArea: {
        silent: true,
        data: [
          [
            { yAxis: 'GenSkill', itemStyle: { color: 'rgba(63,185,80,0.06)' } },
            { yAxis: 'Title', itemStyle: { color: 'rgba(63,185,80,0.06)' } }
          ]
        ],
        label: { show: true, position: 'insideRight', formatter: '完全一致 (13)', color: success, fontSize: 11 }
      }
    }]
  });
  window.addEventListener('resize', function() { chart2.resize(); });
})();