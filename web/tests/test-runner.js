/**
 * San7ModMaker - 前端测试运行器
 * 浏览器端轻量测试框架，无需 Node.js 依赖
 */
(function() {
    'use strict';

    window.TestRunner = {
        tests: [],
        results: { passed: 0, failed: 0, errors: [] },

        /**
         * 注册测试用例
         * @param {string} name - 测试名称
         * @param {Function} fn - 测试函数
         */
        test(name, fn) {
            this.tests.push({ name, fn });
        },

        /**
         * 断言相等
         */
        assertEqual(actual, expected, message) {
            if (actual !== expected) {
                throw new Error(
                    (message || 'assertEqual failed') +
                    '\n  expected: ' + JSON.stringify(expected) +
                    '\n  actual:   ' + JSON.stringify(actual)
                );
            }
        },

        /**
         * 断言为真
         */
        assertTrue(value, message) {
            if (!value) {
                throw new Error((message || 'assertTrue failed') + '\n  value: ' + JSON.stringify(value));
            }
        },

        /**
         * 断言为假
         */
        assertFalse(value, message) {
            if (value) {
                throw new Error((message || 'assertFalse failed') + '\n  value: ' + JSON.stringify(value));
            }
        },

        /**
         * 断言抛出异常
         */
        assertThrows(fn, message) {
            try {
                fn();
                throw new Error((message || 'assertThrows failed') + ': no exception thrown');
            } catch (e) {
                if (e.message && e.message.indexOf('assertThrows failed') === 0) {
                    throw e;
                }
                // 预期的异常，通过
            }
        },

        /**
         * 断言类型
         */
        assertType(value, type, message) {
            const actual = typeof value;
            if (actual !== type) {
                throw new Error(
                    (message || 'assertType failed') +
                    '\n  expected type: ' + type +
                    '\n  actual type:   ' + actual
                );
            }
        },

        /**
         * 运行所有测试
         */
        async run() {
            this.results = { passed: 0, failed: 0, errors: [] };
            const startTime = performance.now();

            for (const t of this.tests) {
                try {
                    await t.fn();
                    this.results.passed++;
                    console.log('✓ PASS:', t.name);
                } catch (e) {
                    this.results.failed++;
                    this.results.errors.push({ name: t.name, error: e.message, stack: e.stack });
                    console.error('✗ FAIL:', t.name, '\n  ', e.message);
                }
            }

            const elapsed = (performance.now() - startTime).toFixed(1);
            console.log(
                '\n========== 测试结果 ==========\n' +
                '通过: ' + this.results.passed +
                '  失败: ' + this.results.failed +
                '  总计: ' + this.tests.length +
                '  耗时: ' + elapsed + 'ms\n' +
                '==============================\n'
            );

            return this.results;
        },

        /**
         * 渲染测试结果到 DOM
         */
        renderTo(containerId) {
            const container = document.getElementById(containerId);
            if (!container) return;

            const total = this.tests.length;
            const passed = this.results.passed;
            const failed = this.results.failed;

            let html = '<div class="test-results">';
            html += '<h2>测试结果</h2>';
            html += '<div class="test-summary">';
            html += '<span class="test-passed">✓ 通过: ' + passed + '</span> ';
            html += '<span class="test-failed">✗ 失败: ' + failed + '</span> ';
            html += '<span class="test-total">总计: ' + total + '</span>';
            html += '</div>';

            if (failed > 0) {
                html += '<div class="test-errors"><h3>失败详情:</h3><ul>';
                for (const err of this.results.errors) {
                    html += '<li><strong>' + this._esc(err.name) + '</strong><pre>' +
                            this._esc(err.error) + '</pre></li>';
                }
                html += '</ul></div>';
            }

            html += '</div>';
            container.innerHTML = html;
        },

        _esc(str) {
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }
    };
})();