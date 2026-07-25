// assets/charts.js
// San7ModMaker MOD制作完成度分析 — 图表
(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var fail = style.getPropertyValue('--fail').trim();
  var warn = style.getPropertyValue('--warn').trim();

  // --- Chart: 综合完成度仪表盘 ---
  var gaugeChart = echarts.init(document.getElementById('chart-gauge'), null, { renderer: 'svg' });
  gaugeChart.setOption({
    animation: false,
    series: [{
      type: 'gauge',
      startAngle: 210,
      endAngle: -30,
      center: ['50%', '55%'],
      radius: '90%',
      min: 0,
      max: 100,
      splitNumber: 10,
      axisLine: {
        show: true,
        lineStyle: {
          width: 18,
          color: [
            [0.6, fail],
            [0.8, warn],
            [1, accent2]
          ]
        }
      },
      pointer: {
        icon: 'path://M12.8,0.7l12,40.1H0.7L12.8,0.7z',
        length: '60%',
        width: 8,
        offsetCenter: [0, '-10%'],
        itemStyle: { color: ink }
      },
      axisTick: { distance: -18, length: 6, lineStyle: { width: 1, color: muted } },
      splitLine: { distance: -22, length: 16, lineStyle: { width: 2, color: muted } },
      axisLabel: { color: muted, fontSize: 11, distance: 30, formatter: '{value}%' },
      anchor: { show: true, showAbove: true, size: 18, itemStyle: { borderWidth: 2, borderColor: muted } },
      title: { offsetCenter: [0, '75%'], fontSize: 14, color: muted },
      detail: {
        valueAnimation: true,
        fontSize: 36,
        fontWeight: '700',
        offsetCenter: [0, '40%'],
        formatter: '{value}%',
        color: accent2
      },
      data: [{ value: 94, name: '综合完成度' }]
    }]
  });

  // --- Chart: 六大维度雷达图 ---
  var radarChart = echarts.init(document.getElementById('chart-radar'), null, { renderer: 'svg' });
  radarChart.setOption({
    animation: false,
    tooltip: { appendToBody: true },
    legend: {
      bottom: 0,
      textStyle: { color: muted, fontSize: 12 },
      data: ['当前完成度', '理想目标']
    },
    radar: {
      center: ['50%', '48%'],
      radius: '65%',
      indicator: [
        { name: '数据表覆盖', max: 100 },
        { name: 'API 完整性', max: 100 },
        { name: '编辑器 UI', max: 100 },
        { name: '素材管理', max: 100 },
        { name: 'MOD 生命周期', max: 100 },
        { name: '端到端工作流', max: 100 },
        { name: '批量/自动化', max: 100 }
      ],
      axisName: { color: muted, fontSize: 11 },
      splitArea: { areaStyle: { color: ['rgba(56,189,248,0.03)', 'rgba(56,189,248,0.03)'] } },
      splitLine: { lineStyle: { color: rule } },
      axisLine: { lineStyle: { color: rule } }
    },
    series: [{
      type: 'radar',
      name: '当前完成度',
      data: [{ value: [95, 95, 92, 88, 88, 88, 90], name: '当前完成度' }],
      symbol: 'circle',
      symbolSize: 6,
      lineStyle: { color: accent, width: 2 },
      areaStyle: { color: accent + '33' },
      itemStyle: { color: accent }
    }, {
      type: 'radar',
      name: '理想目标',
      data: [{ value: [100, 100, 100, 100, 100, 100, 100], name: '理想目标' }],
      symbol: 'none',
      lineStyle: { color: muted, width: 1, type: 'dashed' },
      areaStyle: { color: 'transparent' },
      itemStyle: { color: 'transparent' }
    }]
  });

  // --- Chart: 模块测试覆盖分布 ---
  var covChart = echarts.init(document.getElementById('chart-coverage'), null, { renderer: 'svg' });
  covChart.setOption({
    animation: false,
    tooltip: {
      appendToBody: true,
      formatter: function(p) { return p.name + ': ' + p.value + ' 个模块'; }
    },
    series: [{
      type: 'pie',
      radius: ['45%', '72%'],
      center: ['50%', '50%'],
      label: {
        fontSize: 12,
        color: ink,
        formatter: '{b}\n{d}%'
      },
      labelLine: { lineStyle: { color: rule } },
      emphasis: { disabled: true },
      data: [
        { value: 11, name: '已覆盖测试', itemStyle: { color: accent2 } },
        { value: 5, name: '仅导入验证', itemStyle: { color: warn } },
        { value: 5, name: '零覆盖', itemStyle: { color: fail } }
      ]
    }]
  });

  // Resize
  window.addEventListener('resize', function() {
    gaugeChart.resize();
    radarChart.resize();
    covChart.resize();
  });
})();