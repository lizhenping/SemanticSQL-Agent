"""SemanticSQL-Agent 安装脚本"""

from setuptools import setup, find_packages
from pathlib import Path

# 读取 README
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# 读取 requirements
requirements_file = Path(__file__).parent / "requirements.txt"
requirements = []
if requirements_file.exists():
    with open(requirements_file, "r", encoding="utf-8") as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

setup(
    name="semanticsql-agent",
    version="0.1.0",
    author="lizhenping18@mails.ucas.ac.cn",
    author_email="lizhenping18@mails.ucas.ac.cn",
    description="基于 LangChain 的自然语言到 SQL 转换系统",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/semanticsql-agent",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "prompts": ["templates/**/*.j2"],
    },
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "black>=22.0.0",
            "flake8>=4.0.0",
            "mypy>=1.0.0",
        ],
        "anthropic": ["langchain-anthropic>=0.0.1"],
        "google": ["langchain-google-genai>=0.0.1"],
    },
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "semanticsql=cli:cli",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Database",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    keywords="sql, nlp, langchain, database, query, natural-language",
)