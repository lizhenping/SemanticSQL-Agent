#!/usr/bin/env python3
"""验证scenarios.yaml和operation_mapping.yaml的对齐情况"""

import yaml
from pathlib import Path
from typing import Dict, List, Tuple


def load_yaml(file_path: Path) -> Dict:
    """加载YAML文件"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def extract_scenarios(scenarios_data: Dict) -> Dict[str, List[str]]:
    """从scenarios.yaml提取场景结构"""
    result = {}
    
    for main_key, main_data in scenarios_data['scenarios'].items():
        # 跳过元数据
        if main_key in ['scenario_types', 'total_scenarios', 'total_sub_scenarios']:
            continue
            
        if isinstance(main_data, dict) and 'sub_scenarios' in main_data:
            sub_scenarios = list(main_data['sub_scenarios'].keys())
            result[main_key] = sub_scenarios
    
    return result


def extract_operation_mappings(operation_data: Dict) -> Dict[str, List[str]]:
    """从operation_mapping.yaml提取场景映射"""
    result = {}
    
    if 'scenario_use_case_mapping' in operation_data:
        for main_scenario, sub_mapping in operation_data['scenario_use_case_mapping'].items():
            if isinstance(sub_mapping, dict):
                result[main_scenario] = list(sub_mapping.keys())
    
    return result


def validate_alignment(scenarios: Dict[str, List[str]], 
                      mappings: Dict[str, List[str]]) -> Tuple[bool, List[str]]:
    """验证对齐情况"""
    issues = []
    is_aligned = True
    
    # 检查主场景
    scenarios_main = set(scenarios.keys())
    mappings_main = set(mappings.keys())
    
    missing_in_mappings = scenarios_main - mappings_main
    extra_in_mappings = mappings_main - scenarios_main
    
    if missing_in_mappings:
        is_aligned = False
        for scenario in missing_in_mappings:
            issues.append(f"主场景 '{scenario}' 在 operation_mapping.yaml 中缺失")
    
    if extra_in_mappings:
        is_aligned = False
        for scenario in extra_in_mappings:
            issues.append(f"主场景 '{scenario}' 在 scenarios.yaml 中不存在")
    
    # 检查子场景
    for main_scenario in scenarios_main & mappings_main:
        scenarios_sub = set(scenarios[main_scenario])
        mappings_sub = set(mappings.get(main_scenario, []))
        
        missing_sub = scenarios_sub - mappings_sub
        extra_sub = mappings_sub - scenarios_sub
        
        if missing_sub:
            is_aligned = False
            for sub in missing_sub:
                issues.append(f"子场景 '{main_scenario}.{sub}' 在 operation_mapping.yaml 中缺失")
        
        if extra_sub:
            is_aligned = False
            for sub in extra_sub:
                issues.append(f"子场景 '{main_scenario}.{sub}' 在 scenarios.yaml 中不存在")
    
    return is_aligned, issues


def main():
    """主函数"""
    config_dir = Path(__file__).parent.parent.parent.parent / 'config'
    
    # 加载文件
    scenarios_path = config_dir / 'scenarios.yaml'
    operation_path = config_dir / 'operation_mapping.yaml'
    
    print("验证场景配置对齐情况...")
    print(f"场景文件: {scenarios_path}")
    print(f"映射文件: {operation_path}")
    print("-" * 60)
    
    try:
        scenarios_data = load_yaml(scenarios_path)
        operation_data = load_yaml(operation_path)
        
        # 提取结构
        scenarios = extract_scenarios(scenarios_data)
        mappings = extract_operation_mappings(operation_data)
        
        # 打印结构
        print("\n场景结构 (scenarios.yaml):")
        for main, subs in scenarios.items():
            print(f"  {main}:")
            for sub in subs:
                print(f"    - {sub}")
        
        print("\n映射结构 (operation_mapping.yaml):")
        for main, subs in mappings.items():
            print(f"  {main}:")
            for sub in subs:
                print(f"    - {sub}")
        
        # 验证对齐
        is_aligned, issues = validate_alignment(scenarios, mappings)
        
        print("\n" + "=" * 60)
        if is_aligned:
            print("✅ 两个文件完全对齐！")
        else:
            print("❌ 发现对齐问题:")
            for issue in issues:
                print(f"  - {issue}")
        
        # 统计
        print("\n统计信息:")
        print(f"  主场景数量: scenarios={len(scenarios)}, mappings={len(mappings)}")
        total_subs_scenarios = sum(len(subs) for subs in scenarios.values())
        total_subs_mappings = sum(len(subs) for subs in mappings.values())
        print(f"  子场景总数: scenarios={total_subs_scenarios}, mappings={total_subs_mappings}")
        
    except Exception as e:
        print(f"❌ 错误: {e}")
        return 1
    
    return 0 if is_aligned else 1


if __name__ == '__main__':
    exit(main())