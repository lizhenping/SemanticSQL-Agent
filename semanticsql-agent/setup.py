"""
SemanticSQL Agent Setup Configuration
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

# Read requirements
requirements = []
if (this_directory / "requirements.txt").exists():
    with open(this_directory / "requirements.txt", "r") as f:
        requirements = [line.strip() for line in f 
                       if line.strip() and not line.startswith("#")]

setup(
    name="semanticsql-agent",
    version="2.0.0",
    author="Your Name",
    author_email="your-email@example.com",
    description="An intelligent NL2SQL data generation system based on ReAct agent architecture",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/semanticsql-agent",
    packages=find_packages(exclude=["tests", "tests.*", "examples", "docs"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Database",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.0.0",
            "pre-commit>=3.0.0",
        ],
        "production": [
            "uvicorn>=0.20.0",
            "fastapi>=0.100.0",
            "redis>=4.5.0",
            "celery>=5.2.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "semanticsql=main:cli",
            "semanticsql-agent=main:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "prompts": ["*.yaml"],
        "configs": ["*.yaml"],
    },
    zip_safe=False,
    project_urls={
        "Bug Reports": "https://github.com/yourusername/semanticsql-agent/issues",
        "Source": "https://github.com/yourusername/semanticsql-agent",
        "Documentation": "https://semanticsql-agent.readthedocs.io",
    },
)