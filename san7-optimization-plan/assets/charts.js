(function() {
  var style = getComputedStyle(document.documentElement);
  var accent = style.getPropertyValue('--accent').trim();
  var accent2 = style.getPropertyValue('--accent2').trim();
  var ink = style.getPropertyValue('--ink').trim();
  var muted = style.getPropertyValue('--muted').trim();
  var rule = style.getPropertyValue('--rule').trim();
  var bg2 = style.getPropertyValue('--bg2').trim();
  var warn = style.getPropertyValue('--warn').trim();
  var success = style.getPropertyValue('--success').trim();

  var chartOpts = {
    animation: false,
    textStyle: { color: muted, fontFamily: 'Bricolage, sans-serif' },
    tooltip: { appendToBody: true, backgroundColor: bg2, borderColor: rule, textStyle: { color: ink } }
  };

  // --- Chart 1: API 调用分布 ---
  var chart1 = echarts.init(document.getElementById('chart-api-dist'), null, { renderer: 'svg' });
  chart1.setOption({
    animation: false,
    tooltip: { appendToBody: true, trigger: 'item', backgroundColor: bg2, borderColor: rule, textStyle: { color: ink }, formatter: '{b}: {c} ({d}%)' },
    series: [{
      type: 'pie',
      radius: ['55%', '80%'],
      center: ['50%', '50%'],
      avoidLabelOverlap: false,
      itemStyle: { borderRadius: 4, borderColor: 'transparent', borderWidth: 2 },
      label: { show: true, color: muted, fontSize: 11, formatter: '{b}\n{d}%' },
      data: [
        { value: 271, name: '被调用', itemStyle: { color: accent } },
        { value: 71, name: '未调用(动态)', itemStyle: { color: warn } },
        { value: 25, name: '死代码', itemStyle: { color: accent2 } }
      ]
    }]
  });
  window.addEventListener('resize', function() { chart1.resize(); });

  // --- Chart 2: 重复代码模式分布 ---
  var chart2 = echarts.init(document.getElementById('chart-dup-patterns'), null, { renderer: 'svg' });
  chart2.setOption({
    animation: false,
    tooltip: { appendToBody: true, trigger: 'axis', backgroundColor: bg2, borderColor: rule, textStyle: { color: ink } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'value', axisLine: { lineStyle: { color: rule } }, splitLine: { lineStyle: { color: rule } }, axisLabel: { color: muted, fontSize: 11 } },
    yAxis: { type: 'category', data: ['api_save_*', 'api_load_*', 'api_new_*', 'JsApi桥接', 'uiEditors/cfgEditors'], axisLine: { lineStyle: { color: rule } }, axisLabel: { color: ink, fontSize: 11 } },
    series: [{
      type: 'bar',
      barWidth: 20,
      itemStyle: { borderRadius: [0, 4, 4, 0], color: accent },
      label: { show: true, position: 'right', color: ink, fontSize: 11, formatter: '{c} 个' },
      data: [84, 56, 42, 369, 2]
    }]
  });
  window.addEventListener('resize', function() { chart2.resize(); });

  // --- Chart 3: 文件行数分布 ---
  var chart3 = echarts.init(document.getElementById('chart-file-sizes'), null, { renderer: 'svg' });
  chart3.setOption({
    animation: false,
    tooltip: { appendToBody: true, trigger: 'axis', backgroundColor: bg2, borderColor: rule, textStyle: { color: ink } },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: { type: 'category', data: ['app.js', 'main.py', 'index.html', 'style.css', 'scriptso', 'save_parser', 'exe_patcher', 'validator', 'save_editor', 'pck_manager', 'shp_converter', 'mod_wizard'], axisLine: { lineStyle: { color: rule } }, axisLabel: { color: muted, fontSize: 10, rotate: 30 } },
    yAxis: { type: 'value', axisLine: { lineStyle: { color: rule } }, splitLine: { lineStyle: { color: rule } }, axisLabel: { color: muted, fontSize: 11, formatter: '{value}' } },
    series: [{
      type: 'bar',
      barWidth: 16,
      itemStyle: {
        borderRadius: [4, 4, 0, 0],
        color: function(params) {
          var v = params.value;
          if (v > 8000) return accent2;
          if (v > 1000) return warn;
          return accent;
        }
      },
      label: { show: true, position: 'top', color: ink, fontSize: 10, formatter: '{c}' },
      data: [11611, 8700, 4269, 3203, 1499, 818, 788, 689, 673, 630, 516, 409]
    }]
  });
  window.addEventListener('resize', function() { chart3.resize(); });

  // --- Chart 4: 模块测试覆盖 ---
  var chart4 = echarts.init(document.getElementById('chart-test-coverage'), null, { renderer: 'svg' });
  chart4.setOption({
    animation: false,
    tooltip: { appendToBody: true, trigger: 'axis', backgroundColor: bg2, borderColor: rule, textStyle: { color: ink } },
    legend: { data: ['已测试', '未测试'], textStyle: { color: muted, fontSize: 11 }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '12%', containLabel: true },
    xAxis: { type: 'value', max: 1, axisLine: { lineStyle: { color: rule } }, splitLine: { lineStyle: { color: rule } }, axisLabel: { color: muted, fontSize: 11, formatter: '{value}%' } },
    yAxis: { type: 'category', data: [
      'ini_parser', 'backup_mgr', 'validator', 'encoding_converter', 'save_manager',
      'term_text', 'shp_converter', 'custom_leader', 'atomic_write',
      'save_editor', 'scriptso_analyzer', 'pck_manager', 'mod_wizard', 'exe_patcher',
      'soldier_matrix', 'csv_manager', 'event_templates', 'version_detect',
      'effect_catalog', 'obd_parser'
    ], axisLine: { lineStyle: { color: rule } }, axisLabel: { color: ink, fontSize: 10 } },
    series: [
      {
        name: '已测试',
        type: 'bar',
        stack: 'total',
        barWidth: 14,
        itemStyle: { color: success, borderRadius: [0, 0, 0, 0] },
        data: [1,1,1,1,1, 1,1,1,1, 0,0,0,0,0, 0,0,0,0, 0,0]
      },
      {
        name: '未测试',
        type: 'bar',
        stack: 'total',
        barWidth: 14,
        itemStyle: { color: accent2 + '33', borderRadius: [0, 4, 4, 0] },
        data: [0,0,0,0,0, 0,0,0,0, 1,1,1,1,1, 1,1,1,1, 1,1]
      }
    ]
  });
  window.addEventListener('resize', function() { chart4.resize(); });
})();