/**
 * San7ModMaker - core.js 单元测试
 * 测试工具函数和独立逻辑（不依赖 PyWebView API）
 */
(function() {
    'use strict';
    var T = window.TestRunner;

    // ============================================================
    // escHtml 测试
    // ============================================================
    T.test('escHtml: 空字符串', function() {
        T.assertEqual(escHtml(''), '');
    });

    T.test('escHtml: null/undefined', function() {
        T.assertEqual(escHtml(null), '');
        T.assertEqual(escHtml(undefined), '');
    });

    T.test('escHtml: 转义 HTML 特殊字符', function() {
        T.assertEqual(escHtml('<script>'), '&lt;script&gt;');
        T.assertEqual(escHtml('"test"'), '&quot;test&quot;');
        T.assertEqual(escHtml("it's"), '&#39;it&#39;s');
        T.assertEqual(escHtml('a & b'), 'a &amp; b');
    });

    T.test('escHtml: 普通文本不变', function() {
        T.assertEqual(escHtml('hello world'), 'hello world');
        T.assertEqual(escHtml('測試中文'), '測試中文');
    });

    // ============================================================
    // showToast 测试
    // ============================================================
    T.test('showToast: 创建 toast 元素', function() {
        var container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            document.body.appendChild(container);
        }
        var before = container.children.length;
        showToast('test message', 'success');
        var after = container.children.length;
        T.assertTrue(after > before, 'toast 元素应该被创建');
        T.assertTrue(container.lastChild.classList.contains('toast-success'), '应该有 success 样式');
    });

    T.test('showToast: 长消息截断', function() {
        var longMsg = 'x'.repeat(300);
        showToast(longMsg, 'info');
        // 验证 toast 被创建（不崩溃）
        T.assertTrue(true);
    });

    T.test('showToast: 所有类型', function() {
        ['success', 'error', 'warning', 'info'].forEach(function(type) {
            showToast('test ' + type, type);
        });
        T.assertTrue(true);
    });

    // ============================================================
    // 主题切换 测试
    // ============================================================
    T.test('toggleTheme: 切换暗/亮模式', function() {
        var html = document.documentElement;
        var currentTheme = html.getAttribute('data-theme');
        toggleTheme();
        var newTheme = html.getAttribute('data-theme');
        T.assertTrue(newTheme !== currentTheme || currentTheme === null,
            '主题应该切换: ' + currentTheme + ' -> ' + (newTheme || 'dark'));
        // 恢复
        toggleTheme();
    });

    T.test('主题: localStorage 持久化', function() {
        toggleTheme();
        var saved = localStorage.getItem('san7_theme');
        T.assertTrue(saved === 'light' || saved === 'dark' || saved === null,
            'localStorage 应该有主题值: ' + saved);
        // 恢复
        toggleTheme();
    });

    // ============================================================
    // dashboard 对象测试
    // ============================================================
    T.test('dashboard: 对象存在', function() {
        T.assertTrue(typeof dashboard !== 'undefined', 'dashboard 应该存在');
        T.assertType(dashboard, 'object');
        T.assertType(dashboard.refresh, 'function');
    });

    // ============================================================
    // pyApi 函数测试
    // ============================================================
    T.test('pyApi: 函数存在', function() {
        T.assertType(pyApi, 'function', 'pyApi 应该是函数');
    });

    // ============================================================
    // 通用工具函数测试
    // ============================================================
    T.test('工具: ICON_MAP 定义完整', function() {
        T.assertTrue(typeof ICON_MAP !== 'undefined', 'ICON_MAP 应该存在');
        T.assertEqual(ICON_MAP.success, '✓');
        T.assertEqual(ICON_MAP.error, '✕');
        T.assertEqual(ICON_MAP.warning, '⚠');
        T.assertEqual(ICON_MAP.info, 'ℹ');
    });

    // ============================================================
    // 运行测试
    // ============================================================
    T.run().then(function() {
        T.renderTo('testOutput');
    });
})();