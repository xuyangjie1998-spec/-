"""
三国群英传7 INI 模板引擎
支撑 INI 批量编辑 + 模板化数据生成 + 跨文件一致性验证

功能：
- 模板系统：创建/保存/加载/删除模板（JSON格式）
- 表达式引擎：支持自增/随机/引用/计算/序列等变量表达式
- 批量生成：单模板生成、跨文件联合生成、多请求批量生成
- 跨文件验证：引用完整性、编号唯一性、字段值范围、必填字段
- 数据合并：模板合并、字段覆盖、数据转换
- 预设模板：内置武将/兵种/物品/技能/势力/城池/必杀技模板

依赖：
- core.ini_parser.IniParser：INI 读写
- core.validator.DataValidator：数据校验
"""

import re
import os
import json
import uuid
import random
import sys
import logging
import copy
from collections import OrderedDict
from typing import Dict, List, Any, Optional, Tuple, Union

# PyInstaller 打包后使用 sys._MEIPASS，开发模式使用 __file__
if getattr(sys, 'frozen', False):
    _PROJECT_ROOT = sys._MEIPASS
else:
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from .ini_parser import IniParser, SectionData
from .validator import DataValidator, ValidationResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 模块级常量
# ---------------------------------------------------------------------------

DEFAULT_TEMPLATE_DIR = os.path.join(_PROJECT_ROOT, "data", "templates")

# 表达式模式：{{expression}}
EXPR_PATTERN = re.compile(r"\{\{(.+?)\}\}")

# 表达式类型与对应的解析正则
EXPR_PARSERS = {
    "auto_increment": re.compile(r"^auto_increment(?::(\d+),(\d+))?$"),
    "random": re.compile(r"^random:(\d+),(\d+)$"),
    "random_float": re.compile(r"^random_float:(\d+(?:\.\d+)?),(\d+(?:\.\d+)?)$"),
    "pick": re.compile(r"^pick:(.+)$"),
    "ref": re.compile(r"^ref:([\w.]+)$"),
    "calc": re.compile(r"^calc:(.+)$"),
    "sequence": re.compile(r"^sequence:(\d+),(\d+)$"),
    "uuid": re.compile(r"^uuid$"),
    "counter": re.compile(r"^counter:(\w+)(?::(\d+),(\d+))?$"),
    "if": re.compile(r"^if:(.+),(.+),(.+)$"),
    "pad": re.compile(r"^pad:(\d+),(.+)$"),
    "concat": re.compile(r"^concat:(.+)$"),
    "date": re.compile(r"^date:(\d+)-(\d+)-(\d+)$"),
}


# ---------------------------------------------------------------------------
# IniTemplateEngine
# ---------------------------------------------------------------------------

class IniTemplateEngine:
    """
    INI 模板引擎

    支持模板化批量数据生成、跨文件一致性验证、表达式变量解析。
    模板以 JSON 格式持久化存储，生成的 INI 数据可通过 IniParser 写入文件。

    使用示例::

        engine = IniTemplateEngine()
        engine.create_template("my_general", "general", [{"name": "No", "type": "int", "default": "{{auto_increment:3000,1}}", "required": True}, ...])
        data = engine.generate_from_template("my_general", 5)
        print(data["data"])
    """

    def __init__(self, template_dir: str = None):
        """
        初始化模板引擎

        Args:
            template_dir: 模板存储目录，默认为 data/templates/
        """
        self._template_dir = template_dir or DEFAULT_TEMPLATE_DIR
        self._templates: Dict[str, dict] = OrderedDict()
        self._auto_increment_counters: Dict[str, int] = {}
        self._named_counters: Dict[str, int] = {}
        self._generated_data_cache: Dict[str, List[dict]] = {}

        # 确保模板目录存在
        os.makedirs(self._template_dir, exist_ok=True)

        # 自动加载已有模板
        self._load_all_templates()

        # 验证器实例
        self._validator = DataValidator()
        self._ini_parser = None

    # ========================================================================
    # 模板系统
    # ========================================================================

    def create_template(self, template_name: str, data_type: str,
                        fields: List[dict], rules: dict = None) -> dict:
        """
        创建数据模板

        Args:
            template_name: 模板名称（唯一标识）
            data_type: 数据类型（general/soldier/thing/skill/nation/city/superatk）
            fields: 字段定义列表，每个元素包含:
                - name: 字段名
                - type: 字段类型（int/float/string/bool）
                - default: 默认值（支持表达式如 {{auto_increment}}）
                - range: 可选，值范围 [min, max]
                - required: 是否必填
                - description: 字段描述
                - enum: 可选，枚举值列表
            rules: 生成规则，可包含:
                - start_id: 起始编号
                - id_step: 编号步长
                - section_name: INI section 名称
                - related_templates: 关联模板列表
                - condition: 生成条件（表达式）

        Returns:
            dict: {"success": True, "template": {...}} 或 {"success": False, "error": "..."}
        """
        if not template_name or not template_name.strip():
            return {"success": False, "error": "模板名称不能为空"}

        if not fields:
            return {"success": False, "error": "字段定义不能为空"}

        # 校验字段定义
        for i, field in enumerate(fields):
            if "name" not in field:
                return {"success": False, "error": f"第{i+1}个字段缺少 name 属性"}
            if "type" not in field:
                field["type"] = "string"
            if "default" not in field:
                field["default"] = "" if field["type"] == "string" else "0"
            if "required" not in field:
                field["required"] = False
            valid_types = ("int", "float", "string", "bool", "list", "dict")
            if field["type"] not in valid_types:
                return {"success": False, "error": f"字段 '{field['name']}' 类型 '{field['type']}' 无效，支持: {valid_types}"}

        template = {
            "name": template_name,
            "data_type": data_type,
            "fields": fields,
            "rules": rules or {},
            "version": "1.0",
            "created": self._now_iso(),
            "updated": self._now_iso(),
        }

        # 如果 rules 中没有指定 section_name，根据 data_type 自动推断
        if "section_name" not in template["rules"]:
            template["rules"]["section_name"] = self._infer_section_name(data_type)

        self._templates[template_name] = template
        logger.info(f"创建模板: {template_name} (类型: {data_type}, 字段数: {len(fields)})")

        return {"success": True, "template": template}

    def save_template(self, template: dict, filepath: str = None) -> dict:
        """
        保存模板到 JSON 文件

        Args:
            template: 模板字典
            filepath: 保存路径，不指定则保存到模板目录

        Returns:
            dict: {"success": True, "path": "..."} 或 {"success": False, "error": "..."}
        """
        if not template or "name" not in template:
            return {"success": False, "error": "无效的模板数据"}

        template["updated"] = self._now_iso()

        if filepath:
            save_path = filepath
        else:
            safe_name = re.sub(r"[^\w\-]", "_", template["name"])
            save_path = os.path.join(self._template_dir, f"{safe_name}.json")

        try:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(template, f, ensure_ascii=False, indent=2)
            logger.info(f"模板已保存: {save_path}")
            return {"success": True, "path": save_path}
        except (IOError, OSError) as e:
            logger.error(f"保存模板失败: {e}")
            return {"success": False, "error": str(e)}

    def load_template(self, filepath: str) -> dict:
        """
        从 JSON 文件加载模板

        Args:
            filepath: JSON 文件路径

        Returns:
            dict: {"success": True, "template": {...}} 或 {"success": False, "error": "..."}
        """
        if not os.path.exists(filepath):
            return {"success": False, "error": f"模板文件不存在: {filepath}"}

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                template = json.load(f)
            if "name" not in template:
                return {"success": False, "error": "模板文件缺少 name 字段"}

            self._templates[template["name"]] = template
            logger.info(f"加载模板: {template['name']} (来自 {filepath})")
            return {"success": True, "template": template}
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"加载模板失败: {e}")
            return {"success": False, "error": str(e)}

    def list_templates(self) -> dict:
        """
        列出所有可用模板

        Returns:
            dict: {"success": True, "templates": {...}, "count": N}
        """
        return {
            "success": True,
            "templates": OrderedDict(self._templates),
            "count": len(self._templates),
        }

    def delete_template(self, template_name: str) -> dict:
        """
        删除模板

        Args:
            template_name: 模板名称

        Returns:
            dict: {"success": True} 或 {"success": False, "error": "..."}
        """
        if template_name not in self._templates:
            return {"success": False, "error": f"模板不存在: {template_name}"}

        # 同时删除磁盘文件
        safe_name = re.sub(r"[^\w\-]", "_", template_name)
        filepath = os.path.join(self._template_dir, f"{safe_name}.json")
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
            except OSError as e:
                logger.warning(f"删除模板文件失败: {e}")

        del self._templates[template_name]
        logger.info(f"删除模板: {template_name}")
        return {"success": True}

    # ========================================================================
    # 变量与表达式引擎
    # ========================================================================

    def evaluate_expression(self, expression: str, context: dict) -> Any:
        """
        评估表达式

        支持的表达式类型:
        - {{auto_increment:start,step}} 自增计数器
        - {{random:min,max}} 随机整数
        - {{random_float:min,max}} 随机浮点数
        - {{pick:a,b,c}} 随机选择
        - {{ref:template_name.field_name}} 引用其他模板字段
        - {{calc:expression}} 数学计算
        - {{sequence:start,step}} 序列值
        - {{uuid}} 唯一ID
        - {{counter:name:start,step}} 命名计数器
        - {{if:condition,true_value,false_value}} 条件表达式
        - {{pad:width,value}} 填充到指定宽度
        - {{concat:expr1,expr2,...}} 字符串拼接
        - {{date:year-month-day}} 日期递增

        Args:
            expression: 表达式字符串（不含 {{}} 包裹）
            context: 上下文变量字典

        Returns:
            Any: 计算结果
        """
        expr = expression.strip()

        # auto_increment: {{auto_increment}} 或 {{auto_increment:start,step}}
        match = EXPR_PARSERS["auto_increment"].match(expr)
        if match:
            start = int(match.group(1)) if match.group(1) else 0
            step = int(match.group(2)) if match.group(2) else 1
            key = "__auto_increment__"
            if key not in self._auto_increment_counters:
                self._auto_increment_counters[key] = start
            else:
                self._auto_increment_counters[key] += step
            return self._auto_increment_counters[key]

        # random: {{random:min,max}}
        match = EXPR_PARSERS["random"].match(expr)
        if match:
            lo = int(match.group(1))
            hi = int(match.group(2))
            return random.randint(lo, hi)

        # random_float: {{random_float:min,max}}
        match = EXPR_PARSERS["random_float"].match(expr)
        if match:
            lo = float(match.group(1))
            hi = float(match.group(2))
            return round(random.uniform(lo, hi), 2)

        # pick: {{pick:a,b,c}}
        match = EXPR_PARSERS["pick"].match(expr)
        if match:
            options = [o.strip() for o in match.group(1).split(",")]
            return random.choice(options)

        # ref: {{ref:template_name.field_name}}
        match = EXPR_PARSERS["ref"].match(expr)
        if match:
            ref_path = match.group(1)
            return self._resolve_ref(ref_path, context)

        # calc: {{calc:expression}}
        match = EXPR_PARSERS["calc"].match(expr)
        if match:
            calc_expr = match.group(1)
            return self._safe_eval(calc_expr, context)

        # sequence: {{sequence:start,step}}
        match = EXPR_PARSERS["sequence"].match(expr)
        if match:
            start = int(match.group(1))
            step = int(match.group(2))
            key = "__sequence__"
            if key not in self._auto_increment_counters:
                self._auto_increment_counters[key] = start
            else:
                self._auto_increment_counters[key] += step
            return self._auto_increment_counters[key]

        # uuid: {{uuid}}
        match = EXPR_PARSERS["uuid"].match(expr)
        if match:
            return str(uuid.uuid4())[:8]

        # counter: {{counter:name:start,step}}
        match = EXPR_PARSERS["counter"].match(expr)
        if match:
            counter_name = match.group(1)
            start = int(match.group(2)) if match.group(2) else 0
            step = int(match.group(3)) if match.group(3) else 1
            if counter_name not in self._named_counters:
                self._named_counters[counter_name] = start
            else:
                self._named_counters[counter_name] += step
            return self._named_counters[counter_name]

        # if: {{if:condition,true_value,false_value}}
        match = EXPR_PARSERS["if"].match(expr)
        if match:
            condition = match.group(1).strip()
            true_val = match.group(2).strip()
            false_val = match.group(3).strip()
            result = self._evaluate_condition(condition, context)
            return true_val if result else false_val

        # pad: {{pad:width,value}}
        match = EXPR_PARSERS["pad"].match(expr)
        if match:
            width = int(match.group(1))
            val = match.group(2).strip()
            resolved = self.resolve_variables(val, context)
            return resolved.zfill(width)

        # concat: {{concat:expr1,expr2,...}}
        match = EXPR_PARSERS["concat"].match(expr)
        if match:
            parts = [p.strip() for p in match.group(1).split(",")]
            resolved_parts = [str(self.resolve_variables(p, context)) for p in parts]
            return "".join(resolved_parts)

        # 变量引用: {{var_name}}
        if expr in context:
            return context[expr]

        # 数值表达式短路求值: 形如 "{{auto_increment}} * 100"
        if EXPR_PATTERN.search(expr):
            return self.resolve_variables(expr, context)

        # 尝试作为数字
        try:
            if "." in expr:
                return float(expr)
            return int(expr)
        except (ValueError, TypeError):
            pass

        return expr

    def resolve_variables(self, template_str: str, context: dict) -> str:
        """
        解析模板字符串中的变量

        将 {{expression}} 替换为实际值。支持嵌套表达式。

        Args:
            template_str: 包含变量的模板字符串
            context: 上下文变量字典

        Returns:
            str: 替换后的字符串
        """
        if not isinstance(template_str, str):
            return str(template_str)

        if "{{" not in template_str:
            return template_str

        # 递归解析嵌套表达式：每次找到最内层的 {{...}}（内部不含 {{）进行解析
        max_iterations = 20
        result = template_str
        for _ in range(max_iterations):
            # 查找最内层表达式：{{ 后面紧跟的直到 }} 但中间不含 {{
            inner_pattern = re.compile(r"\{\{([^{}]+)\}\}")
            match = inner_pattern.search(result)
            if not match:
                break
            expr = match.group(1)
            try:
                resolved = str(self.evaluate_expression(expr, context))
            except Exception as e:
                logger.warning(f"表达式评估失败: '{expr}' -> {e}")
                resolved = match.group(0)
            result = result[:match.start()] + resolved + result[match.end():]

        return result

    # ========================================================================
    # 批量生成
    # ========================================================================

    def generate_from_template(self, template_name: str, count: int,
                               overrides: dict = None) -> dict:
        """
        从模板批量生成数据

        Args:
            template_name: 模板名称
            count: 生成数量
            overrides: 可选字段覆盖，如 {"No": "{{auto_increment:4000,1}}", "Name": "测试武将{{counter:n}}"}

        Returns:
            dict: {"success": True, "data": [...], "count": N, "template": "..."}
        """
        if template_name not in self._templates:
            return {"success": False, "error": f"模板不存在: {template_name}"}

        template = self._templates[template_name]
        fields = template.get("fields", [])
        rules = template.get("rules", {})

        if count <= 0:
            return {"success": False, "error": "生成数量必须大于0"}

        # 重置计数器
        self._auto_increment_counters.clear()
        self._named_counters.clear()

        # 应用 overrides 中的规则
        effective_rules = dict(rules)
        if overrides:
            effective_rules.update(overrides.get("__rules__", {}))

        generated = []
        for _ in range(count):
            entry = {}
            context = {
                "template_name": template_name,
                "data_type": template.get("data_type", ""),
                "index": _,
                "count": count,
            }

            for field in fields:
                field_name = field["name"]
                default_value = field.get("default", "")

                # 应用 overrides
                field_overrides = overrides or {}
                if field_name in field_overrides:
                    default_value = field_overrides[field_name]

                # 解析变量
                resolved = self.resolve_variables(str(default_value), context)

                # 类型转换
                resolved = self._cast_value(resolved, field.get("type", "string"))

                entry[field_name] = resolved
                context[field_name] = resolved

            generated.append(entry)

        # 缓存生成结果
        cache_key = f"{template_name}_{count}"
        self._generated_data_cache[cache_key] = generated

        logger.info(f"从模板 '{template_name}' 生成 {count} 条数据")
        return {
            "success": True,
            "data": generated,
            "count": len(generated),
            "template": template_name,
        }

    def generate_cross_file(self, templates: List[dict],
                            relationships: List[dict]) -> dict:
        """
        跨文件批量生成

        同时生成多个关联文件的数据，确保引用一致性。

        Args:
            templates: 模板请求列表，每个元素包含:
                - template: 模板名称
                - count: 生成数量
                - overrides: 可选字段覆盖
                - output_label: 输出标签（如 "general", "defskill", "termtext"）
            relationships: 关联关系列表，每个元素包含:
                - source: 源模板标签
                - target: 目标模板标签
                - source_field: 源字段名
                - target_field: 目标字段名
                - type: 关系类型（one_to_one/one_to_many/many_to_one）

        Returns:
            dict: {"success": True, "data": {"general": [...], "defskill": [...], ...}}
        """
        if not templates:
            return {"success": False, "error": "模板列表不能为空"}

        # 第一阶段：生成所有模板数据
        generated_data = OrderedDict()
        for req in templates:
            tpl_name = req.get("template", "")
            tpl_count = req.get("count", 1)
            tpl_overrides = req.get("overrides", {})
            tpl_label = req.get("output_label", tpl_name)

            result = self.generate_from_template(tpl_name, tpl_count, tpl_overrides)
            if not result.get("success"):
                return {"success": False, "error": f"生成模板 '{tpl_name}' 失败: {result.get('error')}"}

            generated_data[tpl_label] = result["data"]

        # 第二阶段：应用关联关系，确保引用一致性
        for rel in relationships:
            source_label = rel.get("source", "")
            target_label = rel.get("target", "")
            source_field = rel.get("source_field", "")
            target_field = rel.get("target_field", "")
            rel_type = rel.get("type", "one_to_one")

            source_data = generated_data.get(source_label, [])
            target_data = generated_data.get(target_label, [])

            if not source_data or not target_data:
                continue

            if rel_type == "one_to_one":
                # 一对一：逐一对应
                for i, (src_entry, tgt_entry) in enumerate(zip(source_data, target_data)):
                    if i < len(source_data) and i < len(target_data):
                        if source_field in src_entry and target_field in tgt_entry:
                            tgt_entry[target_field] = src_entry[source_field]

            elif rel_type == "one_to_many":
                # 一对多：一个源对应多个目标
                for i, src_entry in enumerate(source_data):
                    for j, tgt_entry in enumerate(target_data):
                        if j % len(source_data) == i % len(source_data):
                            if source_field in src_entry and target_field in tgt_entry:
                                tgt_entry[target_field] = src_entry[source_field]

            elif rel_type == "many_to_one":
                # 多对一：多个源对应一个目标
                for i, tgt_entry in enumerate(target_data):
                    if i < len(source_data):
                        src_entry = source_data[i]
                        if source_field in src_entry and target_field in tgt_entry:
                            tgt_entry[target_field] = src_entry[source_field]

        # 缓存所有生成结果
        for label, data in generated_data.items():
            self._generated_data_cache[label] = data

        logger.info(f"跨文件生成完成: {len(generated_data)} 个数据集")
        return {
            "success": True,
            "data": generated_data,
            "labels": list(generated_data.keys()),
        }

    def batch_generate(self, requests: List[dict]) -> dict:
        """
        批量生成请求

        每个请求指定模板、数量、输出目标。返回所有生成结果。

        Args:
            requests: 请求列表，每个元素包含:
                - template: 模板名称
                - count: 生成数量
                - overrides: 可选字段覆盖
                - output_target: 输出目标（如 "General01.ini"）

        Returns:
            dict: {"success": True, "results": [...], "total": N}
        """
        if not requests:
            return {"success": False, "error": "请求列表不能为空"}

        results = []
        total = 0

        for i, req in enumerate(requests):
            tpl_name = req.get("template", "")
            tpl_count = req.get("count", 1)
            tpl_overrides = req.get("overrides", {})
            output_target = req.get("output_target", "")

            result = self.generate_from_template(tpl_name, tpl_count, tpl_overrides)
            if result.get("success"):
                total += result["count"]
                results.append({
                    "index": i,
                    "template": tpl_name,
                    "output_target": output_target,
                    "count": result["count"],
                    "data": result["data"],
                    "success": True,
                })
            else:
                results.append({
                    "index": i,
                    "template": tpl_name,
                    "output_target": output_target,
                    "count": 0,
                    "data": [],
                    "success": False,
                    "error": result.get("error", "未知错误"),
                })

        logger.info(f"批量生成完成: {total} 条数据, {len(results)} 个请求")
        return {
            "success": True,
            "results": results,
            "total": total,
        }

    # ========================================================================
    # 跨文件一致性验证
    # ========================================================================

    def validate_cross_file(self, generated_data: dict) -> dict:
        """
        验证生成数据的跨文件一致性

        检查项:
        - 引用完整性（武将引用的兵种存在、物品引用的技能存在等）
        - 编号唯一性
        - 字段值范围
        - 必填字段

        Args:
            generated_data: 生成的数据，格式: {"general": [...], "soldier": [...], ...}

        Returns:
            dict: {"success": True, "valid": True/False, "errors": [...], "warnings": [...], "summary": {...}}
        """
        errors = []
        warnings = []

        # 收集所有数据
        generals = generated_data.get("general", [])
        soldiers = generated_data.get("soldier", [])
        things = generated_data.get("thing", [])
        defskill = generated_data.get("defskill", [])
        nations = generated_data.get("nation", [])
        cities = generated_data.get("city", [])
        superatk = generated_data.get("superatk", [])
        bfmagic = generated_data.get("bfmagic", [])
        sfmagic = generated_data.get("sfmagic", [])
        genskill = generated_data.get("genskill", [])
        armyskill = generated_data.get("armyskill", [])
        armygroupskill = generated_data.get("armygroupskill", [])
        termtext = generated_data.get("termtext", [])

        # 1. 编号唯一性检查
        for label, data in generated_data.items():
            dups = self._check_duplicate_ids(data)
            for dup in dups:
                errors.append({
                    "severity": "error",
                    "category": "duplicate_id",
                    "message": dup,
                    "source": label,
                })

        # 2. 必填字段检查
        for label, data in generated_data.items():
            missing = self._check_required_fields(label, data)
            errors.extend(missing)

        # 3. 引用完整性检查
        if generals and soldiers:
            soldier_ids = {str(s.get("No", "")) for s in soldiers}
            for i, gen in enumerate(generals):
                for field in ["BFSoldier", "BFSoldier1", "BFSoldier2"]:
                    sid = str(gen.get(field, ""))
                    if sid and sid != "0" and sid not in soldier_ids:
                        errors.append({
                            "severity": "error",
                            "category": "broken_reference",
                            "message": f"武将 #{gen.get('No', i)} 引用的兵种编号 {sid} 不存在",
                            "source": "general",
                            "field": field,
                            "index": i,
                        })

        if generals and things:
            thing_ids = {str(t.get("No", "")) for t in things}
            for i, gen in enumerate(generals):
                for field in ["Weapon", "Horse"]:
                    tid = str(gen.get(field, ""))
                    if tid and tid != "0" and tid not in thing_ids:
                        warnings.append({
                            "severity": "warning",
                            "category": "broken_reference",
                            "message": f"武将 #{gen.get('No', i)} 引用的物品编号 {tid} 不存在",
                            "source": "general",
                            "field": field,
                            "index": i,
                        })

        # 4. 武将-DefSkill 一致性
        if generals and defskill:
            gen_nos = {str(g.get("No", "")) for g in generals}
            defskill_nos = {str(d.get("No", "")) for d in defskill}
            for g in generals:
                no = str(g.get("No", ""))
                if no and no not in defskill_nos:
                    warnings.append({
                        "severity": "warning",
                        "category": "missing_defskill",
                        "message": f"武将 #{no} ({g.get('Name', '')}) 缺少 DefSkill 配置",
                        "source": "defskill",
                        "field": "No",
                    })

        # 5. 技能引用检查
        if generals and superatk:
            superatk_ids = {str(s.get("NO", "")) for s in superatk}
            for i, gen in enumerate(generals):
                ss = str(gen.get("SuperSkill", "")).strip()
                if ss and ss != "0" and ss not in superatk_ids:
                    errors.append({
                        "severity": "error",
                        "category": "broken_skill_ref",
                        "message": f"武将 #{gen.get('No', i)} 引用的必杀技编号 {ss} 不存在",
                        "source": "general",
                        "field": "SuperSkill",
                        "index": i,
                    })

        # 6. DefSkill 技能槽位引用检查
        if defskill:
            bfmagic_ids = {str(m.get("No", "")) for m in bfmagic}
            for d in defskill:
                no = str(d.get("No", ""))
                bfm = str(d.get("BFMagic", "")).strip()
                if bfm and bfmagic_ids:
                    for rid in bfm.split(","):
                        rid = rid.strip()
                        if rid and rid != "0" and rid not in bfmagic_ids:
                            errors.append({
                                "severity": "error",
                                "category": "broken_skill_ref",
                                "message": f"DefSkill #{no} 引用的武将技编号 {rid} 不存在",
                                "source": "defskill",
                                "field": "BFMagic",
                            })

        # 7. TermText 引用检查
        if termtext:
            termtext_ids = {str(t.get("id", "")) for t in termtext}
            for label, data in generated_data.items():
                if label == "termtext":
                    continue
                for i, entry in enumerate(data):
                    string_id = str(entry.get("stringID_FullName", ""))
                    if string_id and string_id not in termtext_ids:
                        warnings.append({
                            "severity": "warning",
                            "category": "missing_termtext",
                            "message": f"{label} #{entry.get('No', i)} 的 stringID_FullName={string_id} 在 TermText 中不存在",
                            "source": label,
                            "field": "stringID_FullName",
                            "index": i,
                        })

        # 8. 数值范围检查
        range_issues = self._check_value_ranges(generated_data)
        warnings.extend(range_issues)

        # 汇总
        has_errors = len(errors) > 0
        summary = {
            "total_issues": len(errors) + len(warnings),
            "errors": len(errors),
            "warnings": len(warnings),
        }

        logger.info(f"跨文件验证完成: {summary['errors']} 错误, {summary['warnings']} 警告")
        return {
            "success": True,
            "valid": not has_errors,
            "errors": errors,
            "warnings": warnings,
            "summary": summary,
        }

    def check_references(self, data: dict, reference_map: dict) -> dict:
        """
        检查引用完整性

        给定数据和引用映射，检查所有引用目标是否存在。

        Args:
            data: 数据字典，格式: {"source_label": [...]}
            reference_map: 引用映射，格式:
                {"source_label": {"source_field": "target_label:target_field"}}

        Returns:
            dict: {"success": True, "broken_refs": [...], "valid": True/False}
        """
        broken = []

        for source_label, field_map in reference_map.items():
            source_data = data.get(source_label, [])
            if not source_data:
                continue

            for source_field, target_ref in field_map.items():
                parts = target_ref.split(":", 1)
                if len(parts) != 2:
                    broken.append({
                        "severity": "error",
                        "message": f"引用映射格式错误: {target_ref}",
                        "source": source_label,
                        "field": source_field,
                    })
                    continue

                target_label, target_field = parts
                target_data = data.get(target_label, [])
                if not target_data:
                    continue

                target_ids = {str(t.get(target_field, "")) for t in target_data}

                for i, entry in enumerate(source_data):
                    ref_val = str(entry.get(source_field, ""))
                    if ref_val and ref_val != "0" and ref_val not in target_ids:
                        broken.append({
                            "severity": "error",
                            "category": "broken_reference",
                            "message": f"{source_label} #{entry.get('No', i)} 的 {source_field}={ref_val} 引用了不存在的 {target_label}.{target_field}",
                            "source": source_label,
                            "field": source_field,
                            "index": i,
                            "ref_value": ref_val,
                            "target": target_label,
                        })

        logger.info(f"引用检查完成: {len(broken)} 个断裂引用")
        return {
            "success": True,
            "broken_refs": broken,
            "valid": len(broken) == 0,
        }

    def consistency_report(self, generated_data: dict) -> dict:
        """
        生成一致性报告

        包含所有警告和错误，按类别分组。

        Args:
            generated_data: 生成的数据

        Returns:
            dict: {"success": True, "report": {...}}
        """
        validation = self.validate_cross_file(generated_data)
        ref_check = self.check_references(generated_data, self._build_reference_map(generated_data))

        # 按类别分组
        errors_by_category = {}
        for err in validation.get("errors", []):
            cat = err.get("category", "unknown")
            if cat not in errors_by_category:
                errors_by_category[cat] = []
            errors_by_category[cat].append(err)

        warnings_by_category = {}
        for warn in validation.get("warnings", []):
            cat = warn.get("category", "unknown")
            if cat not in warnings_by_category:
                warnings_by_category[cat] = []
            warnings_by_category[cat].append(warn)

        # 数据统计
        data_stats = {}
        for label, data in generated_data.items():
            data_stats[label] = {
                "count": len(data),
                "fields": list(data[0].keys()) if data else [],
            }

        report = {
            "generated_at": self._now_iso(),
            "data_stats": data_stats,
            "summary": validation.get("summary", {}),
            "errors_by_category": errors_by_category,
            "warnings_by_category": warnings_by_category,
            "broken_references": ref_check.get("broken_refs", []),
            "overall_valid": validation.get("valid", False) and ref_check.get("valid", False),
        }

        logger.info(f"一致性报告生成完成: {'通过' if report['overall_valid'] else '存在问题'}")
        return {"success": True, "report": report}

    # ========================================================================
    # 数据合并与转换
    # ========================================================================

    def merge_templates(self, base_template: str,
                        overlay_templates: List[str]) -> dict:
        """
        合并多个模板

        基模板提供默认值，覆盖模板覆盖特定字段。

        Args:
            base_template: 基模板名称
            overlay_templates: 覆盖模板名称列表

        Returns:
            dict: {"success": True, "merged": {...}} 或 {"success": False, "error": "..."}
        """
        if base_template not in self._templates:
            return {"success": False, "error": f"基模板不存在: {base_template}"}

        base = copy.deepcopy(self._templates[base_template])
        base_fields = base.get("fields", [])
        base_rules = base.get("rules", {})

        # 构建基模板字段索引
        field_index = OrderedDict()
        for f in base_fields:
            field_index[f["name"]] = f

        for overlay_name in overlay_templates:
            if overlay_name not in self._templates:
                logger.warning(f"覆盖模板不存在，跳过: {overlay_name}")
                continue

            overlay = self._templates[overlay_name]
            overlay_fields = overlay.get("fields", [])
            overlay_rules = overlay.get("rules", {})

            # 覆盖字段
            for f in overlay_fields:
                field_index[f["name"]] = f

            # 覆盖规则
            base_rules.update(overlay_rules)

        merged = {
            "name": f"{base_template}_merged",
            "data_type": base.get("data_type", ""),
            "fields": list(field_index.values()),
            "rules": base_rules,
            "version": "1.0",
            "created": self._now_iso(),
            "updated": self._now_iso(),
            "merged_from": [base_template] + overlay_templates,
        }

        logger.info(f"合并模板: {[base_template] + overlay_templates} -> {merged['name']}")
        return {"success": True, "merged": merged}

    def apply_overrides(self, data: dict, overrides: dict) -> dict:
        """
        应用字段覆盖

        支持点号路径（如 "general.Stats.WStr"）进行深层覆盖。

        Args:
            data: 原始数据字典
            overrides: 覆盖字典，键支持点号路径

        Returns:
            dict: {"success": True, "data": {...}} 或 {"success": False, "error": "..."}
        """
        if not data:
            return {"success": False, "error": "数据不能为空"}

        result = copy.deepcopy(data)

        for path, value in overrides.items():
            self._set_nested(result, path, value)

        logger.info(f"应用覆盖: {len(overrides)} 个字段")
        return {"success": True, "data": result}

    def transform_data(self, data: dict, transformations: List[dict]) -> dict:
        """
        数据转换

        支持的类型转换:
        - type_cast: 类型转换（int/float/string/bool）
        - value_map: 值映射（{"old": "new"}）
        - condition: 条件转换（{"condition": "expr", "action": "set_field", "field": "x", "value": "y"}）
        - rename: 字段重命名（{"from": "old_name", "to": "new_name"}）
        - remove: 删除字段（{"field": "name"}）
        - format: 格式化（{"field": "name", "format": "pattern"}）

        Args:
            data: 原始数据字典
            transformations: 转换规则列表

        Returns:
            dict: {"success": True, "data": {...}, "applied": N}
        """
        if not data:
            return {"success": False, "error": "数据不能为空"}

        result = copy.deepcopy(data)
        applied = 0

        for transform in transformations:
            t_type = transform.get("type", "")

            if t_type == "type_cast":
                field = transform.get("field", "")
                cast_type = transform.get("cast_type", "string")
                if field in result:
                    result[field] = self._cast_value(result[field], cast_type)
                    applied += 1

            elif t_type == "value_map":
                field = transform.get("field", "")
                mapping = transform.get("mapping", {})
                if field in result and str(result[field]) in mapping:
                    result[field] = mapping[str(result[field])]
                    applied += 1

            elif t_type == "condition":
                condition = transform.get("condition", "")
                action = transform.get("action", "set_field")
                if self._evaluate_condition_simple(condition, result):
                    if action == "set_field":
                        result[transform["field"]] = transform.get("value", "")
                    elif action == "remove_field":
                        result.pop(transform.get("field", ""), None)
                    applied += 1

            elif t_type == "rename":
                old_name = transform.get("from", "")
                new_name = transform.get("to", "")
                if old_name in result:
                    result[new_name] = result.pop(old_name)
                    applied += 1

            elif t_type == "remove":
                field = transform.get("field", "")
                if field in result:
                    del result[field]
                    applied += 1

            elif t_type == "format":
                field = transform.get("field", "")
                fmt = transform.get("format", "{}")
                if field in result:
                    try:
                        result[field] = fmt.format(result[field])
                        applied += 1
                    except (KeyError, ValueError):
                        pass

        logger.info(f"数据转换完成: {applied} 个转换应用")
        return {"success": True, "data": result, "applied": applied}

    # ========================================================================
    # 预设模板
    # ========================================================================

    @staticmethod
    def get_preset_templates() -> dict:
        """
        获取内置预设模板

        包括:
        - new_general: 新增武将
        - new_soldier: 新增兵种
        - new_item: 新增物品
        - new_skill: 新增技能（武将特性）
        - new_nation: 新增势力
        - new_city: 新增城池
        - new_superatk: 新增必杀技

        Returns:
            dict: {"success": True, "templates": {...}}
        """
        presets = {
            "new_general": {
                "name": "new_general",
                "data_type": "general",
                "description": "新增武将模板",
                "fields": [
                    {"name": "No", "type": "int", "required": True, "default": "{{auto_increment:3000,1}}", "description": "武将编号", "range": [0, 9999]},
                    {"name": "Name", "type": "string", "required": True, "default": "新武将{{counter:idx}}", "description": "武将姓名"},
                    {"name": "FaceID", "type": "int", "required": True, "default": "{{random:1,100}}", "description": "头像编号", "range": [0, 9999]},
                    {"name": "WStr", "type": "int", "required": True, "default": "{{random:40,95}}", "description": "武力", "range": [0, 255]},
                    {"name": "Int", "type": "int", "required": True, "default": "{{random:40,95}}", "description": "智力", "range": [0, 255]},
                    {"name": "HP", "type": "int", "required": True, "default": "{{random:200,500}}", "description": "体力", "range": [0, 9999]},
                    {"name": "MP", "type": "int", "required": True, "default": "{{random:150,400}}", "description": "技力", "range": [0, 9999]},
                    {"name": "Morale", "type": "int", "default": "50", "description": "初始士气", "range": [0, 100]},
                    {"name": "Loyal", "type": "int", "default": "{{random:40,80}}", "description": "义理", "range": [0, 100]},
                    {"name": "Relation", "type": "int", "default": "{{random:0,255}}", "description": "相性", "range": [0, 255]},
                    {"name": "Sex", "type": "int", "default": "{{pick:0,1}}", "description": "性别(0=女,1=男)", "range": [0, 1]},
                    {"name": "Race", "type": "int", "default": "0", "description": "种族", "range": [0, 99]},
                    {"name": "Weapon", "type": "int", "default": "{{random:1,50}}", "description": "初始武器编号", "range": [0, 9999]},
                    {"name": "Horse", "type": "int", "default": "0", "description": "初始坐骑编号", "range": [0, 9999]},
                    {"name": "BFSoldier", "type": "int", "default": "1", "description": "初始兵种1", "range": [0, 67]},
                    {"name": "BFSoldier1", "type": "int", "default": "0", "description": "初始兵种2", "range": [0, 67]},
                    {"name": "BFSoldier2", "type": "int", "default": "0", "description": "可选兵种3", "range": [0, 67]},
                    {"name": "Life", "type": "int", "default": "0", "description": "寿命", "range": [0, 9999]},
                    {"name": "HorseSkill", "type": "int", "default": "0", "description": "骑术", "range": [0, 255]},
                    {"name": "Formation", "type": "int", "default": "1", "description": "初始阵型", "range": [0, 99]},
                    {"name": "Sword", "type": "int", "default": "{{random:0,50}}", "description": "剑熟练度", "range": [0, 255]},
                    {"name": "Spear", "type": "int", "default": "{{random:0,50}}", "description": "枪熟练度", "range": [0, 255]},
                    {"name": "Bow", "type": "int", "default": "{{random:0,50}}", "description": "弓熟练度", "range": [0, 255]},
                    {"name": "Blade", "type": "int", "default": "{{random:0,50}}", "description": "刀熟练度", "range": [0, 255]},
                    {"name": "Fan", "type": "int", "default": "{{random:0,50}}", "description": "扇熟练度", "range": [0, 255]},
                    {"name": "SuperSkill", "type": "int", "default": "0", "description": "专属必杀技编号", "range": [0, 9999]},
                    {"name": "SuperSkillExp", "type": "string", "default": "210,210,210", "description": "必杀熟练度"},
                    {"name": "FRelation", "type": "string", "default": "", "description": "土匪友好度"},
                    {"name": "Father", "type": "int", "default": "0", "description": "父亲编号", "range": [0, 9999]},
                    {"name": "Spouse", "type": "int", "default": "0", "description": "配偶编号", "range": [0, 9999]},
                    {"name": "Lord", "type": "int", "default": "0", "description": "自动投奔君主编号", "range": [0, 9999]},
                    {"name": "Respawn", "type": "int", "default": "0", "description": "是否复活", "range": [0, 1]},
                    {"name": "IsFamous", "type": "int", "default": "0", "description": "是否名将", "range": [0, 1]},
                    {"name": "ResID", "type": "string", "default": "011", "description": "战场/大地图造型编号"},
                    {"name": "stringID_FullName", "type": "int", "default": "{{auto_increment:35000,1}}", "description": "全名字符串ID", "range": [0, 99999]},
                    {"name": "stringID_SecondName", "type": "int", "default": "{{auto_increment:35000,1}}", "description": "次名字符串ID", "range": [0, 99999]},
                    {"name": "stringID_FirstName", "type": "int", "default": "{{auto_increment:35000,1}}", "description": "首名字符串ID", "range": [0, 99999]},
                    {"name": "stringID_CallMySelf", "type": "int", "default": "{{auto_increment:35000,1}}", "description": "自称字符串ID", "range": [0, 99999]},
                    {"name": "stringID_Appellation", "type": "int", "default": "{{auto_increment:35000,1}}", "description": "称号字符串ID", "range": [0, 99999]},
                    {"name": "DefaultTitle", "type": "int", "default": "0", "description": "初始官职编号", "range": [0, 9999]},
                    {"name": "IsEvent", "type": "int", "default": "0", "description": "是否特殊武将", "range": [0, 1]},
                    {"name": "ExtraType", "type": "int", "default": "0", "description": "特殊武将属性", "range": [0, 9999]},
                    {"name": "EventType", "type": "int", "default": "0", "description": "特殊武将类型", "range": [0, 9999]},
                    {"name": "OffsetZ", "type": "int", "default": "0", "description": "造型高度位差", "range": [-999, 999]},
                    {"name": "IsUsed", "type": "int", "default": "1", "description": "是否启用", "range": [0, 1]},
                ],
                "rules": {
                    "section_name": "GENERAL",
                    "start_id": 3000,
                    "id_step": 1,
                    "related_templates": ["new_defskill", "new_termtext_general"],
                },
            },
            "new_soldier": {
                "name": "new_soldier",
                "data_type": "soldier",
                "description": "新增兵种模板",
                "fields": [
                    {"name": "No", "type": "int", "required": True, "default": "{{auto_increment:100,1}}", "description": "兵种编号", "range": [0, 9999]},
                    {"name": "Name", "type": "string", "required": True, "default": "新兵种{{counter:idx}}", "description": "兵种名称"},
                    {"name": "Special", "type": "int", "default": "0", "description": "特殊特性", "range": [0, 9999]},
                    {"name": "OrderNo", "type": "int", "default": "{{auto_increment:100,1}}", "description": "排序编号", "range": [0, 9999]},
                    {"name": "ObjID", "type": "int", "default": "{{random:1,20}}", "description": "模型ID", "range": [0, 9999]},
                    {"name": "Data01", "type": "int", "default": "0", "description": "升级兵种相关1", "range": [0, 9999]},
                    {"name": "Data02", "type": "int", "default": "0", "description": "升级兵种相关2", "range": [0, 9999]},
                    {"name": "Data03", "type": "int", "default": "0", "description": "升级兵种相关3", "range": [0, 9999]},
                    {"name": "SuperHit", "type": "int", "default": "0", "description": "特殊效果机率", "range": [0, 100]},
                    {"name": "Feature", "type": "int", "default": "0", "description": "特性标识", "range": [0, 9999]},
                    {"name": "Sex", "type": "int", "default": "0", "description": "性别限制", "range": [0, 2]},
                    {"name": "DieMode", "type": "int", "default": "0", "description": "死亡模式", "range": [0, 99]},
                    {"name": "Rank", "type": "int", "default": "0", "description": "兵种阶级", "range": [0, 99]},
                    {"name": "Upgrade", "type": "int", "default": "0", "description": "升级目标", "range": [0, 9999]},
                    {"name": "OffsetZ", "type": "int", "default": "0", "description": "Z轴偏移", "range": [-999, 999]},
                    {"name": "SizeX", "type": "int", "default": "1", "description": "碰撞体积X", "range": [0, 99]},
                    {"name": "Str", "type": "float", "default": "1.0", "description": "力量系数", "range": [0.0, 99.0]},
                    {"name": "Int", "type": "float", "default": "1.0", "description": "智力系数", "range": [0.0, 99.0]},
                    {"name": "Life", "type": "int", "required": True, "default": "{{random:50,200}}", "description": "生命值", "range": [0, 9999]},
                    {"name": "Speed", "type": "int", "default": "{{random:30,70}}", "description": "速度", "range": [0, 100]},
                    {"name": "Interval", "type": "int", "default": "{{random:30,90}}", "description": "攻击间隔", "range": [0, 999]},
                    {"name": "DetectRangeMin", "type": "int", "default": "0", "description": "最小侦测范围", "range": [0, 999]},
                    {"name": "DetectRangeMax", "type": "int", "default": "0", "description": "最大侦测范围", "range": [0, 999]},
                    {"name": "Weapon", "type": "int", "default": "0", "description": "副武器种类", "range": [0, 99]},
                    {"name": "WeaponSpeed", "type": "int", "default": "0", "description": "投掷速度", "range": [0, 999]},
                    {"name": "BasePower", "type": "int", "required": True, "default": "{{random:5,30}}", "description": "初始攻击力", "range": [0, 9999]},
                    {"name": "AddPower", "type": "int", "required": True, "default": "{{random:1,10}}", "description": "防御力", "range": [0, 9999]},
                    {"name": "Height", "type": "int", "default": "0", "description": "兵种高度", "range": [0, 999]},
                    {"name": "Horse", "type": "int", "default": "0", "description": "坐骑类型", "range": [0, 99]},
                    {"name": "Type", "type": "int", "default": "{{pick:0,1,2,3}}", "description": "兵种类型", "range": [0, 99]},
                    {"name": "Color", "type": "int", "default": "0", "description": "兵种颜色", "range": [0, 9999]},
                    {"name": "IsUsed", "type": "int", "default": "1", "description": "是否启用", "range": [0, 1]},
                ],
                "rules": {
                    "section_name": "SOLDIER",
                    "start_id": 100,
                    "id_step": 1,
                    "related_templates": ["new_termtext_soldier"],
                },
            },
            "new_item": {
                "name": "new_item",
                "data_type": "thing",
                "description": "新增物品模板",
                "fields": [
                    {"name": "No", "type": "int", "required": True, "default": "{{auto_increment:2000,1}}", "description": "物品编号", "range": [0, 9999]},
                    {"name": "Name", "type": "string", "required": True, "default": "新物品{{counter:idx}}", "description": "物品名称"},
                    {"name": "Type", "type": "int", "required": True, "default": "2", "description": "物品类型(1消耗品2武器3坐骑4道具5锻造书)", "range": [1, 5]},
                    {"name": "Param1", "type": "int", "default": "0", "description": "武器系别", "range": [0, 99]},
                    {"name": "Param2", "type": "int", "default": "0", "description": "武器特效/弓射程", "range": [0, 99]},
                    {"name": "Param3", "type": "int", "default": "0", "description": "手握姿势", "range": [0, 99]},
                    {"name": "Param4", "type": "int", "default": "0", "description": "武器特性", "range": [0, 99]},
                    {"name": "Param5", "type": "int", "default": "0", "description": "预留参数", "range": [0, 99]},
                    {"name": "ScriptNo", "type": "int", "default": "0", "description": "特殊效果脚本", "range": [0, 9999]},
                    {"name": "ScriptHit", "type": "int", "default": "0", "description": "特殊效果发动概率", "range": [0, 100]},
                    {"name": "SFResID", "type": "int", "default": "0", "description": "大地图造型编号", "range": [0, 9999]},
                    {"name": "BFResID", "type": "int", "default": "0", "description": "战场模型编号", "range": [0, 9999]},
                    {"name": "BFWResID", "type": "int", "default": "0", "description": "战场光影编号", "range": [0, 9999]},
                    {"name": "IconID", "type": "int", "default": "0", "description": "物品图标编号", "range": [0, 9999]},
                    {"name": "IsRare", "type": "int", "default": "0", "description": "稀有程度", "range": [0, 6]},
                    {"name": "Count", "type": "int", "default": "1", "description": "堆叠数量", "range": [0, 99]},
                    {"name": "Level", "type": "int", "default": "{{random:1,30}}", "description": "使用等级要求", "range": [0, 99]},
                    {"name": "HP", "type": "int", "default": "0", "description": "体力上限加成", "range": [0, 9999]},
                    {"name": "MP", "type": "int", "default": "0", "description": "技力上限加成", "range": [0, 9999]},
                    {"name": "Str", "type": "int", "default": "0", "description": "武力加成", "range": [0, 999]},
                    {"name": "Int", "type": "int", "default": "0", "description": "智力加成", "range": [0, 999]},
                    {"name": "Speed", "type": "int", "default": "0", "description": "速度加成", "range": [0, 100]},
                    {"name": "Loyal", "type": "int", "default": "0", "description": "忠诚加成", "range": [0, 100]},
                    {"name": "Rate", "type": "int", "default": "50", "description": "出现几率", "range": [0, 100]},
                    {"name": "ResponseTime", "type": "int", "default": "0", "description": "攻击间隔", "range": [-99, 99]},
                    {"name": "Price", "type": "int", "default": "{{random:100,5000}}", "description": "购买价格", "range": [0, 99999]},
                    {"name": "BFMagic01", "type": "int", "default": "0", "description": "附加武将技1", "range": [0, 9999]},
                    {"name": "BFMagic02", "type": "int", "default": "0", "description": "附加武将技2", "range": [0, 9999]},
                    {"name": "BFMagic03", "type": "int", "default": "0", "description": "附加武将技3", "range": [0, 9999]},
                    {"name": "BFMagic04", "type": "int", "default": "0", "description": "附加武将技4", "range": [0, 9999]},
                    {"name": "BFMagic05", "type": "int", "default": "0", "description": "附加武将技5", "range": [0, 9999]},
                    {"name": "SFMagic01", "type": "int", "default": "0", "description": "附加军师技1", "range": [0, 9999]},
                    {"name": "SFMagic02", "type": "int", "default": "0", "description": "附加军师技2", "range": [0, 9999]},
                    {"name": "SuperAttack", "type": "int", "default": "0", "description": "附加必杀技编号", "range": [0, 9999]},
                    {"name": "SoldierType", "type": "int", "default": "0", "description": "附加兵种", "range": [0, 9999]},
                    {"name": "Formation", "type": "int", "default": "0", "description": "附加阵形", "range": [0, 9999]},
                    {"name": "GenSkill01", "type": "int", "default": "0", "description": "附加个人特性1", "range": [0, 999]},
                    {"name": "GenSkill02", "type": "int", "default": "0", "description": "附加个人特性2", "range": [0, 999]},
                    {"name": "ArmySkill01", "type": "int", "default": "0", "description": "附加主将特性1", "range": [0, 999]},
                    {"name": "ArmySkill02", "type": "int", "default": "0", "description": "附加主将特性2", "range": [0, 999]},
                    {"name": "AGSkill01", "type": "int", "default": "0", "description": "附加元帅特性1", "range": [0, 999]},
                    {"name": "AGSkill02", "type": "int", "default": "0", "description": "附加元帅特性2", "range": [0, 999]},
                    {"name": "Age01", "type": "int", "default": "1", "description": "剧本1出现", "range": [0, 1]},
                    {"name": "Age02", "type": "int", "default": "1", "description": "剧本2出现", "range": [0, 1]},
                    {"name": "Age03", "type": "int", "default": "1", "description": "剧本3出现", "range": [0, 1]},
                    {"name": "Age04", "type": "int", "default": "1", "description": "剧本4出现", "range": [0, 1]},
                    {"name": "Age05", "type": "int", "default": "1", "description": "剧本5出现", "range": [0, 1]},
                    {"name": "Age06", "type": "int", "default": "1", "description": "剧本6出现", "range": [0, 1]},
                    {"name": "Age07", "type": "int", "default": "1", "description": "剧本7出现", "range": [0, 1]},
                    {"name": "Age08", "type": "int", "default": "1", "description": "剧本8出现", "range": [0, 1]},
                    {"name": "IsUsed", "type": "int", "default": "1", "description": "是否启用", "range": [0, 1]},
                    {"name": "General", "type": "int", "default": "0", "description": "专属武将编号", "range": [0, 9999]},
                ],
                "rules": {
                    "section_name": "THING",
                    "start_id": 2000,
                    "id_step": 1,
                    "related_templates": ["new_termtext_thing"],
                },
            },
            "new_skill": {
                "name": "new_skill",
                "data_type": "defskill",
                "description": "新增武将特性模板（DefSkill.ini）",
                "fields": [
                    {"name": "No", "type": "int", "required": True, "default": "{{auto_increment:3000,1}}", "description": "武将编号", "range": [0, 9999]},
                    {"name": "Name", "type": "string", "required": True, "default": "新武将{{counter:idx}}", "description": "武将姓名"},
                    {"name": "BFMagic", "type": "string", "default": "0,0,0,0,0,0,0,0,0,0", "description": "武将技(10槽位)"},
                    {"name": "SFMagic", "type": "string", "default": "0,0,0,0,0,0,0,0,0,0", "description": "军师技(10槽位)"},
                    {"name": "GenSkill", "type": "string", "default": "0,0,0,0,0,0,0,0,0,0", "description": "个人特性(10槽位)"},
                    {"name": "ArmySkill", "type": "string", "default": "0,0,0,0,0,0,0,0,0,0", "description": "主将特性(10槽位)"},
                    {"name": "ArmyGroupSkill", "type": "string", "default": "0,0,0,0,0,0,0,0,0,0", "description": "元帅特性(10槽位)"},
                ],
                "rules": {
                    "section_name": "GenSkill",
                    "start_id": 3000,
                    "id_step": 1,
                    "related_templates": ["new_general"],
                },
            },
            "new_nation": {
                "name": "new_nation",
                "data_type": "nation",
                "description": "新增势力模板",
                "fields": [
                    {"name": "No", "type": "int", "required": True, "default": "{{auto_increment:50,1}}", "description": "势力编号", "range": [0, 99]},
                    {"name": "Name", "type": "string", "required": True, "default": "新势力{{counter:idx}}", "description": "势力名称"},
                    {"name": "Color", "type": "int", "default": "{{random:0,20}}", "description": "旗帜颜色编号", "range": [0, 99]},
                    {"name": "Lord", "type": "int", "default": "{{ref:new_general.No}}", "description": "君主武将编号", "range": [0, 9999]},
                    {"name": "Advisor", "type": "int", "default": "0", "description": "军师武将编号", "range": [0, 9999]},
                    {"name": "Capital", "type": "int", "default": "0", "description": "首都城池编号", "range": [0, 999]},
                    {"name": "Cities", "type": "string", "default": "", "description": "初始城池列表"},
                    {"name": "Generals", "type": "string", "default": "", "description": "初始武将列表"},
                    {"name": "Money", "type": "int", "default": "{{random:5000,30000}}", "description": "初始金钱", "range": [0, 999999]},
                    {"name": "Food", "type": "int", "default": "{{random:20000,100000}}", "description": "初始粮草", "range": [0, 999999]},
                    {"name": "Soldier", "type": "int", "default": "{{random:5000,20000}}", "description": "初始兵力", "range": [0, 999999]},
                    {"name": "BGM", "type": "int", "default": "8", "description": "背景音乐编号", "range": [0, 99]},
                    {"name": "IsUsed", "type": "int", "default": "1", "description": "是否启用", "range": [0, 1]},
                ],
                "rules": {
                    "section_name": "NATION",
                    "start_id": 50,
                    "id_step": 1,
                },
            },
            "new_city": {
                "name": "new_city",
                "data_type": "city",
                "description": "新增城池模板",
                "fields": [
                    {"name": "No", "type": "int", "required": True, "default": "{{auto_increment:200,1}}", "description": "城池编号", "range": [0, 999]},
                    {"name": "Name", "type": "string", "required": True, "default": "新城池{{counter:idx}}", "description": "城池名称"},
                    {"name": "BuildingType", "type": "int", "default": "1", "description": "建筑类型", "range": [0, 99]},
                    {"name": "BuildingStyle", "type": "int", "default": "0", "description": "建筑风格", "range": [0, 99]},
                    {"name": "Connect00", "type": "string", "default": "", "description": "连接城池1"},
                    {"name": "Connect01", "type": "string", "default": "", "description": "连接城池2"},
                    {"name": "Connect02", "type": "string", "default": "", "description": "连接城池3"},
                    {"name": "Connect03", "type": "string", "default": "", "description": "连接城池4"},
                    {"name": "Connect04", "type": "string", "default": "", "description": "连接城池5"},
                    {"name": "Connect05", "type": "string", "default": "", "description": "连接城池6"},
                    {"name": "Connect06", "type": "string", "default": "", "description": "连接城池7"},
                    {"name": "Connect07", "type": "string", "default": "", "description": "连接城池8"},
                    {"name": "Connect08", "type": "string", "default": "", "description": "连接城池9"},
                    {"name": "Connect09", "type": "string", "default": "", "description": "连接城池10"},
                    {"name": "IsUsed", "type": "int", "default": "1", "description": "是否启用", "range": [0, 1]},
                ],
                "rules": {
                    "section_name": "CITY",
                    "start_id": 200,
                    "id_step": 1,
                },
            },
            "new_superatk": {
                "name": "new_superatk",
                "data_type": "superatk",
                "description": "新增必杀技模板",
                "fields": [
                    {"name": "NO", "type": "int", "required": True, "default": "{{auto_increment:500,1}}", "description": "必杀技编号", "range": [0, 9999]},
                    {"name": "Name", "type": "string", "required": True, "default": "新必杀技{{counter:idx}}", "description": "必杀技名称"},
                    {"name": "HitRatio", "type": "float", "default": "{{random:30,70}}", "description": "发动几率(%)", "range": [0, 100]},
                    {"name": "General01", "type": "float", "default": "1.0", "description": "初学-对武将伤害倍率", "range": [0, 999]},
                    {"name": "General02", "type": "float", "default": "1.25", "description": "进阶-对武将伤害倍率", "range": [0, 999]},
                    {"name": "General03", "type": "float", "default": "1.5", "description": "精通-对武将伤害倍率", "range": [0, 999]},
                    {"name": "Soldier01", "type": "float", "default": "1.0", "description": "初学-对士兵伤害倍率", "range": [0, 999]},
                    {"name": "Soldier02", "type": "float", "default": "1.25", "description": "进阶-对士兵伤害倍率", "range": [0, 999]},
                    {"name": "Soldier03", "type": "float", "default": "1.5", "description": "精通-对士兵伤害倍率", "range": [0, 999]},
                    {"name": "Special01", "type": "float", "default": "1.0", "description": "初学-对设施伤害倍率", "range": [0, 999]},
                    {"name": "Special02", "type": "float", "default": "1.25", "description": "进阶-对设施伤害倍率", "range": [0, 999]},
                    {"name": "Special03", "type": "float", "default": "1.5", "description": "精通-对设施伤害倍率", "range": [0, 999]},
                    {"name": "IsUsed", "type": "int", "default": "1", "description": "是否启用", "range": [0, 1]},
                ],
                "rules": {
                    "section_name": "SuperAtk",
                    "start_id": 500,
                    "id_step": 1,
                },
            },
        }

        return {"success": True, "templates": presets}

    @staticmethod
    def get_info() -> dict:
        """
        获取模块信息

        Returns:
            dict: 模块元信息
        """
        return {
            "module": "ini_template",
            "name": "INI 模板引擎",
            "version": "1.0.0",
            "description": "支撑 INI 批量编辑 + 模板化数据生成 + 跨文件一致性验证",
            "author": "San7ModMaker",
            "dependencies": ["core.ini_parser", "core.validator"],
            "features": [
                "模板系统（创建/保存/加载/删除）",
                "表达式引擎（自增/随机/引用/计算/序列等）",
                "批量生成（单模板/跨文件/批量请求）",
                "跨文件一致性验证（引用完整性/编号唯一性/字段范围/必填字段）",
                "数据合并与转换（模板合并/字段覆盖/类型转换）",
                "内置预设模板（武将/兵种/物品/技能/势力/城池/必杀技）",
            ],
            "supported_expressions": [
                "auto_increment:start,step",
                "random:min,max",
                "random_float:min,max",
                "pick:a,b,c",
                "ref:template_name.field_name",
                "calc:expression",
                "sequence:start,step",
                "uuid",
                "counter:name:start,step",
                "if:condition,true_value,false_value",
                "pad:width,value",
                "concat:expr1,expr2,...",
                "date:year-month-day",
            ],
        }

    # ========================================================================
    # 内部辅助方法
    # ========================================================================

    def _load_all_templates(self):
        """加载模板目录中所有 JSON 模板文件"""
        if not os.path.exists(self._template_dir):
            return
        try:
            for fname in os.listdir(self._template_dir):
                if fname.endswith(".json"):
                    filepath = os.path.join(self._template_dir, fname)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            template = json.load(f)
                        if "name" in template:
                            self._templates[template["name"]] = template
                    except (json.JSONDecodeError, IOError) as e:
                        logger.warning(f"加载模板文件失败: {filepath} -> {e}")
        except OSError as e:
            logger.warning(f"遍历模板目录失败: {e}")

    @staticmethod
    def _infer_section_name(data_type: str) -> str:
        """根据数据类型推断 INI section 名称"""
        mapping = {
            "general": "GENERAL",
            "soldier": "SOLDIER",
            "thing": "THING",
            "defskill": "GenSkill",
            "nation": "NATION",
            "city": "CITY",
            "superatk": "SuperAtk",
            "bfmagic": "BFMagic",
            "sfmagic": "SFMagic",
            "genskill": "GenSkill",
            "armyskill": "ArmySkill",
            "armygroupskill": "ArmyGroupSkill",
            "title": "TITLE",
            "termtext": "TermText",
            "formation": "Formation",
            "genlv": "GenLV",
            "itemenhance": "ITEMENHANCE",
            "dialogue": "Dialogue",
            "history": "History",
            "buildingpos": "BuildingPos",
            "citysellitem": "CitySellItem",
            "citypos": "CityPos",
            "chessformat": "ChessFormat",
        }
        return mapping.get(data_type.lower(), data_type.upper())

    @staticmethod
    def _cast_value(value: Any, cast_type: str) -> Any:
        """类型转换"""
        if cast_type == "int":
            try:
                return int(float(str(value)))
            except (ValueError, TypeError):
                return 0
        elif cast_type == "float":
            try:
                return float(str(value))
            except (ValueError, TypeError):
                return 0.0
        elif cast_type == "bool":
            if isinstance(value, bool):
                return value
            if isinstance(value, str):
                return value.lower() in ("true", "1", "yes")
            return bool(value)
        elif cast_type == "list":
            if isinstance(value, list):
                return value
            if isinstance(value, str):
                return [v.strip() for v in value.split(",") if v.strip()]
            return [value]
        elif cast_type == "dict":
            if isinstance(value, dict):
                return value
            return {}
        else:
            return str(value) if value is not None else ""

    def _resolve_ref(self, ref_path: str, context: dict) -> Any:
        """
        解析引用 {{ref:template_name.field_name}}

        尝试从上下文中查找引用值
        """
        parts = ref_path.split(".")
        if len(parts) >= 2:
            template_name = parts[0]
            field_name = ".".join(parts[1:])

            # 检查缓存
            cache_key = f"{template_name}_*"
            for key, data in self._generated_data_cache.items():
                if key.startswith(template_name.split("_")[0]):
                    if data and field_name in data[0]:
                        idx = context.get("index", 0)
                        if idx < len(data):
                            return data[idx].get(field_name, ref_path)

            # 尝试从上下文中查找
            context_key = f"__ref_{template_name}_{field_name}__"
            if context_key in context:
                return context[context_key]

        return ref_path

    @staticmethod
    def _safe_eval(expression: str, context: dict) -> Any:
        """
        安全的数学表达式求值

        支持基本运算: + - * / % **
        支持变量引用: context中的变量
        """
        # 替换变量
        expr = expression
        for key, value in context.items():
            if isinstance(value, (int, float)) and re.search(rf"\b{re.escape(key)}\b", expr):
                expr = expr.replace(key, str(value))

        # 允许数字、基本运算符、空格、括号、小数点
        if not re.match(r"^[\d\s+\-*/%().,]+$", expr):
            # 尝试更宽松的匹配：允许浮点数
            if not re.match(r"^[\d\s+\-*/%().,.eE]+$", expr):
                raise ValueError(f"不安全的表达式: {expression}")

        try:
            import ast
            return ast.literal_eval(expr)
        except Exception as e:
            logger.warning(f"表达式求值失败: {expression} -> {e}")
            return expression

    @staticmethod
    def _evaluate_condition(condition: str, context: dict) -> bool:
        """评估条件表达式"""
        # 替换变量
        for key, value in context.items():
            if isinstance(value, (int, float, bool)):
                condition = condition.replace(key, str(value))
            elif isinstance(value, str):
                condition = condition.replace(key, f"'{value}'")

        # 安全检查
        safe_ops = ["==", "!=", ">=", "<=", ">", "<", "and", "or", "not", "True", "False", "in"]
        condition_lower = condition.lower()
        for op in safe_ops:
            condition_lower = condition_lower.replace(op.lower(), "")

        if not re.match(r"^[\d\s+\-*/%().,'\"\[\]a-zA-Z_]+$", condition_lower):
            logger.warning(f"条件表达式包含不安全字符: {condition}")
            return False

        try:
            import ast
            result = ast.literal_eval(condition)
            return bool(result)
        except Exception as e:
            logger.warning(f"条件求值失败: {condition} -> {e}")
            return False

    @staticmethod
    def _evaluate_condition_simple(condition: str, data: dict) -> bool:
        """简化版条件求值（用于 transform_data）"""
        # 替换 data 中的字段
        expr = condition
        for key, value in data.items():
            if isinstance(value, (int, float)):
                expr = expr.replace(key, str(value))
            elif isinstance(value, str):
                expr = expr.replace(key, f"'{value}'")

        try:
            import ast
            return bool(ast.literal_eval(expr))
        except Exception:
            return False

    @staticmethod
    def _set_nested(data: dict, path: str, value: Any):
        """按点号路径设置嵌套字典值"""
        parts = path.split(".")
        current = data
        for part in parts[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value

    @staticmethod
    def _check_duplicate_ids(data: List[dict]) -> List[str]:
        """检查重复编号，返回错误信息列表"""
        results = []
        seen = {}
        for i, entry in enumerate(data):
            no = str(entry.get("No", entry.get("NO", "")))
            if not no:
                continue
            if no in seen:
                results.append(f"编号 {no} 重复出现（第{seen[no]+1}条 vs 第{i+1}条）")
            else:
                seen[no] = i
        return results

    def _check_required_fields(self, label: str, data: List[dict]) -> List[dict]:
        """检查必填字段"""
        results = []
        # 尝试从模板获取字段定义
        template = self._templates.get(label) or self._templates.get(f"new_{label}")
        if not template:
            return results

        required_fields = [f["name"] for f in template.get("fields", []) if f.get("required")]
        for i, entry in enumerate(data):
            for field in required_fields:
                val = entry.get(field, None)
                if val is None or str(val).strip() == "":
                    results.append({
                        "severity": "error",
                        "category": "missing_required",
                        "message": f"{label} #{entry.get('No', i)} 缺少必填字段 {field}",
                        "source": label,
                        "field": field,
                        "index": i,
                    })
        return results

    def _check_value_ranges(self, generated_data: dict) -> List[dict]:
        """检查字段值范围"""
        results = []
        range_map = DataValidator.RANGE_RULES

        for label, data in generated_data.items():
            schema_type = self._label_to_schema_type(label)
            rules = range_map.get(schema_type, {})
            if not rules:
                continue

            for i, entry in enumerate(data):
                for field, value in entry.items():
                    if field in rules:
                        min_val, max_val = rules[field]
                        try:
                            v = int(float(str(value)))
                            if v < min_val or v > max_val:
                                results.append({
                                    "severity": "warning",
                                    "category": "value_overflow",
                                    "message": f"{label} #{entry.get('No', i)} 字段 {field}={v} 超出范围 [{min_val}, {max_val}]",
                                    "source": label,
                                    "field": field,
                                    "index": i,
                                })
                        except (ValueError, TypeError):
                            pass
        return results

    @staticmethod
    def _label_to_schema_type(label: str) -> str:
        """将数据标签映射到 schema 类型"""
        mapping = {
            "general": "general",
            "soldier": "soldier",
            "thing": "thing",
            "item": "thing",
            "superatk": "superatk",
            "bfmagic": "bfmagic",
            "title": "title",
            "city": "city",
            "genlv": "genlv",
        }
        return mapping.get(label.lower(), label.lower())

    def _build_reference_map(self, generated_data: dict) -> dict:
        """根据生成数据自动构建引用映射"""
        ref_map = {}

        # 已知的跨文件引用关系
        if "general" in generated_data and "soldier" in generated_data:
            ref_map.setdefault("general", {}).update({
                "BFSoldier": "soldier:No",
                "BFSoldier1": "soldier:No",
                "BFSoldier2": "soldier:No",
            })

        if "general" in generated_data and "thing" in generated_data:
            ref_map.setdefault("general", {}).update({
                "Weapon": "thing:No",
                "Horse": "thing:No",
            })

        if "general" in generated_data and "superatk" in generated_data:
            ref_map.setdefault("general", {}).update({
                "SuperSkill": "superatk:NO",
            })

        if "thing" in generated_data and "superatk" in generated_data:
            ref_map.setdefault("thing", {}).update({
                "SuperAttack": "superatk:NO",
            })

        if "nation" in generated_data and "general" in generated_data:
            ref_map.setdefault("nation", {}).update({
                "Lord": "general:No",
                "Advisor": "general:No",
            })

        if "defskill" in generated_data and "general" in generated_data:
            ref_map.setdefault("defskill", {}).update({
                "No": "general:No",
            })

        return ref_map

    @staticmethod
    def _now_iso() -> str:
        """获取当前时间 ISO 格式字符串"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")