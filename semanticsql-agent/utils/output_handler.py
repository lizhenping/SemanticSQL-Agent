"""
输出处理器 - 支持多种格式的数据输出
"""

import json
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Union, Optional
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class OutputHandler:
    """输出处理器"""
    
    SUPPORTED_FORMATS = ['json', 'jsonl', 'csv', 'tsv', 'parquet', 'excel', 'markdown']
    
    def __init__(self, output_dir: str = "output"):
        """
        初始化输出处理器
        
        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def save(self, 
             data: Union[List[Dict], Dict, pd.DataFrame],
             filename: str,
             format: str = 'json',
             **kwargs) -> str:
        """
        保存数据到文件
        
        Args:
            data: 要保存的数据
            filename: 文件名（不含扩展名）
            format: 输出格式
            **kwargs: 额外参数
            
        Returns:
            保存的文件路径
        """
        if format not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {format}. Supported: {self.SUPPORTED_FORMATS}")
        
        # 添加时间戳（如果需要）
        if kwargs.get('add_timestamp', False):
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{filename}_{timestamp}"
        
        # 根据格式处理
        if format == 'json':
            return self._save_json(data, filename, **kwargs)
        elif format == 'jsonl':
            return self._save_jsonl(data, filename, **kwargs)
        elif format == 'csv':
            return self._save_csv(data, filename, **kwargs)
        elif format == 'tsv':
            return self._save_csv(data, filename, delimiter='\t', **kwargs)
        elif format == 'parquet':
            return self._save_parquet(data, filename, **kwargs)
        elif format == 'excel':
            return self._save_excel(data, filename, **kwargs)
        elif format == 'markdown':
            return self._save_markdown(data, filename, **kwargs)
        else:
            raise ValueError(f"Format {format} not implemented")
    
    def _save_json(self, data: Any, filename: str, **kwargs) -> str:
        """保存为JSON格式"""
        filepath = self.output_dir / f"{filename}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(
                data,
                f,
                indent=kwargs.get('indent', 2),
                ensure_ascii=kwargs.get('ensure_ascii', False),
                default=str  # 处理datetime等特殊类型
            )
        
        logger.info(f"Data saved to {filepath}")
        return str(filepath)
    
    def _save_jsonl(self, data: List[Dict], filename: str, **kwargs) -> str:
        """保存为JSONL格式（每行一个JSON）"""
        filepath = self.output_dir / f"{filename}.jsonl"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for item in data:
                json.dump(item, f, ensure_ascii=False, default=str)
                f.write('\n')
        
        logger.info(f"Data saved to {filepath}")
        return str(filepath)
    
    def _save_csv(self, data: Union[List[Dict], pd.DataFrame], 
                  filename: str, delimiter: str = ',', **kwargs) -> str:
        """保存为CSV/TSV格式"""
        extension = 'tsv' if delimiter == '\t' else 'csv'
        filepath = self.output_dir / f"{filename}.{extension}"
        
        # 转换为DataFrame
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        else:
            df = data
        
        df.to_csv(
            filepath,
            sep=delimiter,
            index=kwargs.get('index', False),
            encoding='utf-8'
        )
        
        logger.info(f"Data saved to {filepath}")
        return str(filepath)
    
    def _save_parquet(self, data: Union[List[Dict], pd.DataFrame], 
                      filename: str, **kwargs) -> str:
        """保存为Parquet格式"""
        filepath = self.output_dir / f"{filename}.parquet"
        
        # 转换为DataFrame
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            df = pd.DataFrame([data])
        else:
            df = data
        
        df.to_parquet(
            filepath,
            index=kwargs.get('index', False),
            compression=kwargs.get('compression', 'snappy')
        )
        
        logger.info(f"Data saved to {filepath}")
        return str(filepath)
    
    def _save_excel(self, data: Union[List[Dict], pd.DataFrame, Dict[str, pd.DataFrame]], 
                    filename: str, **kwargs) -> str:
        """保存为Excel格式"""
        filepath = self.output_dir / f"{filename}.xlsx"
        
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            if isinstance(data, dict) and all(isinstance(v, (pd.DataFrame, list)) for v in data.values()):
                # 多个sheet
                for sheet_name, sheet_data in data.items():
                    if isinstance(sheet_data, list):
                        df = pd.DataFrame(sheet_data)
                    else:
                        df = sheet_data
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
            else:
                # 单个sheet
                if isinstance(data, list):
                    df = pd.DataFrame(data)
                elif isinstance(data, dict):
                    df = pd.DataFrame([data])
                else:
                    df = data
                df.to_excel(writer, sheet_name='Sheet1', index=False)
        
        logger.info(f"Data saved to {filepath}")
        return str(filepath)
    
    def _save_markdown(self, data: Union[List[Dict], Dict], filename: str, **kwargs) -> str:
        """保存为Markdown格式"""
        filepath = self.output_dir / f"{filename}.md"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            # 写入标题
            title = kwargs.get('title', 'Data Export')
            f.write(f"# {title}\n\n")
            
            # 写入元数据
            f.write(f"**Generated at**: {datetime.now().isoformat()}\n\n")
            
            # 转换数据为表格
            if isinstance(data, list) and data:
                # 表格头
                headers = list(data[0].keys())
                f.write("| " + " | ".join(headers) + " |\n")
                f.write("| " + " | ".join(["---"] * len(headers)) + " |\n")
                
                # 表格内容
                for row in data:
                    values = [str(row.get(h, "")) for h in headers]
                    f.write("| " + " | ".join(values) + " |\n")
            
            elif isinstance(data, dict):
                # 键值对形式
                for key, value in data.items():
                    f.write(f"**{key}**: {value}\n\n")
        
        logger.info(f"Data saved to {filepath}")
        return str(filepath)
    
    def convert_format(self, 
                      input_file: str,
                      output_format: str,
                      output_filename: str = None) -> str:
        """
        转换文件格式
        
        Args:
            input_file: 输入文件路径
            output_format: 输出格式
            output_filename: 输出文件名
            
        Returns:
            输出文件路径
        """
        input_path = Path(input_file)
        
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")
        
        # 读取数据
        if input_path.suffix == '.json':
            with open(input_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif input_path.suffix == '.jsonl':
            data = []
            with open(input_path, 'r', encoding='utf-8') as f:
                for line in f:
                    data.append(json.loads(line))
        elif input_path.suffix in ['.csv', '.tsv']:
            delimiter = '\t' if input_path.suffix == '.tsv' else ','
            data = pd.read_csv(input_path, sep=delimiter).to_dict('records')
        elif input_path.suffix == '.parquet':
            data = pd.read_parquet(input_path).to_dict('records')
        elif input_path.suffix == '.xlsx':
            data = pd.read_excel(input_path).to_dict('records')
        else:
            raise ValueError(f"Unsupported input format: {input_path.suffix}")
        
        # 保存为新格式
        if output_filename is None:
            output_filename = input_path.stem
        
        return self.save(data, output_filename, output_format)
    
    def format_for_training(self, 
                           data: List[Dict],
                           format_type: str = 'openai') -> List[Dict]:
        """
        格式化为训练数据格式
        
        Args:
            data: 原始数据
            format_type: 格式类型 (openai, huggingface, alpaca)
            
        Returns:
            格式化后的数据
        """
        formatted_data = []
        
        for item in data:
            if format_type == 'openai':
                # OpenAI微调格式
                formatted_item = {
                    "messages": [
                        {"role": "system", "content": "You are a SQL expert."},
                        {"role": "user", "content": item.get('question', '')},
                        {"role": "assistant", "content": item.get('sql', '')}
                    ]
                }
            
            elif format_type == 'huggingface':
                # HuggingFace格式
                formatted_item = {
                    "input": item.get('question', ''),
                    "output": item.get('sql', ''),
                    "instruction": "Convert the natural language query to SQL."
                }
            
            elif format_type == 'alpaca':
                # Alpaca格式
                formatted_item = {
                    "instruction": "Convert the following natural language query to SQL",
                    "input": item.get('question', ''),
                    "output": item.get('sql', '')
                }
            
            else:
                raise ValueError(f"Unknown format type: {format_type}")
            
            # 添加元数据
            if 'metadata' in item:
                formatted_item['metadata'] = item['metadata']
            
            formatted_data.append(formatted_item)
        
        return formatted_data
    
    def generate_report(self, 
                       data: List[Dict],
                       report_type: str = 'summary') -> Dict[str, Any]:
        """
        生成数据报告
        
        Args:
            data: 数据列表
            report_type: 报告类型
            
        Returns:
            报告内容
        """
        report = {
            "generated_at": datetime.now().isoformat(),
            "total_count": len(data),
            "report_type": report_type
        }
        
        if report_type == 'summary':
            # 基础统计
            report["statistics"] = {
                "total": len(data),
                "valid": sum(1 for d in data if d.get('valid', False)),
                "invalid": sum(1 for d in data if not d.get('valid', True))
            }
            
            # 难度分布
            if any('difficulty' in d for d in data):
                difficulties = [d.get('difficulty', 'unknown') for d in data]
                report["difficulty_distribution"] = {
                    diff: difficulties.count(diff) 
                    for diff in set(difficulties)
                }
            
            # 质量分数
            if any('quality_score' in d for d in data):
                scores = [d.get('quality_score', 0) for d in data if 'quality_score' in d]
                report["quality_metrics"] = {
                    "average": sum(scores) / len(scores) if scores else 0,
                    "min": min(scores) if scores else 0,
                    "max": max(scores) if scores else 0
                }
        
        elif report_type == 'detailed':
            # 详细分析
            df = pd.DataFrame(data)
            report["columns"] = list(df.columns)
            report["dtypes"] = df.dtypes.to_dict()
            report["missing_values"] = df.isnull().sum().to_dict()
            report["unique_values"] = {col: df[col].nunique() for col in df.columns}
            
            # 数值列统计
            numeric_cols = df.select_dtypes(include=['number']).columns
            if len(numeric_cols) > 0:
                report["numeric_stats"] = df[numeric_cols].describe().to_dict()
        
        return report


# 便捷函数
def save_json(data: Any, filename: str, output_dir: str = "output") -> str:
    """保存为JSON"""
    handler = OutputHandler(output_dir)
    return handler.save(data, filename, 'json')


def save_jsonl(data: List[Dict], filename: str, output_dir: str = "output") -> str:
    """保存为JSONL"""
    handler = OutputHandler(output_dir)
    return handler.save(data, filename, 'jsonl')


def save_csv(data: Union[List[Dict], pd.DataFrame], filename: str, output_dir: str = "output") -> str:
    """保存为CSV"""
    handler = OutputHandler(output_dir)
    return handler.save(data, filename, 'csv')


def format_for_openai(data: List[Dict]) -> List[Dict]:
    """格式化为OpenAI训练格式"""
    handler = OutputHandler()
    return handler.format_for_training(data, 'openai')


def format_for_huggingface(data: List[Dict]) -> List[Dict]:
    """格式化为HuggingFace训练格式"""
    handler = OutputHandler()
    return handler.format_for_training(data, 'huggingface')