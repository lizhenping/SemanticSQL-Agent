"""
SemanticSQL Agent CLI - Simplified command line interface
Based on the design specification
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

import click
import yaml

from config.settings import Settings
from config.database import DatabaseConfig
from utils.database import DatabaseManager
from agent.smart_sql_agent import SmartSQLAgent


# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


@click.group()
@click.version_option(version="2.0.0")
@click.option('--config', '-c', help='Configuration file path')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, config: Optional[str], verbose: bool):
    """SemanticSQL Agent - Natural Language to SQL System"""
    ctx.ensure_object(dict)
    ctx.obj['config_path'] = config
    ctx.obj['verbose'] = verbose
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)


@cli.command()
@click.argument("query")
@click.option('--config', '-c', help='Configuration file path')
@click.option('--model', '-m', help='LLM model to use')
@click.option('--host', help='Database host')
@click.option('--port', type=int, help='Database port')
@click.option('--user', help='Database username')
@click.option('--password', help='Database password')
@click.option('--database', '-d', help='Database name')
@click.option('--save-result', '-s', help='Save result to file')
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def run(ctx, query: str, config: Optional[str], model: Optional[str],
        host: Optional[str], port: Optional[int], user: Optional[str],
        password: Optional[str], database: Optional[str], 
        save_result: Optional[str], verbose: bool):
    """Execute a natural language query"""
    
    click.echo(f"Query: {query}")
    click.echo("=" * 50)
    
    try:
        # Load configuration
        if config and Path(config).exists():
            # Load from config file
            settings = Settings()
            with open(config, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            
            # Create database config from file
            db_config_data = config_data.get('database', {})
            db_config = DatabaseConfig(**db_config_data)
            
            # Override with command line args
            if model:
                settings.llm_model = model
            if host:
                db_config.host = host
            if port:
                db_config.port = port
            if user:
                db_config.username = user
            if password:
                db_config.password = password
            if database:
                db_config.database = database
            if verbose:
                settings.verbose = True
        else:
            # Use settings from environment/defaults
            settings = Settings()
            db_config = DatabaseConfig.from_env()
        
        # Initialize database
        db_manager = DatabaseManager(db_config)
        if not db_manager.initialize():
            click.echo("Error: Database connection failed", err=True)
            sys.exit(1)
        
        # Create and run agent
        agent = SmartSQLAgent(settings, db_config)
        result = agent.query(query)
        
        # Display result
        if result.success:
            click.echo("✓ Query successful")
            if result.sql:
                click.echo(f"\nSQL:\n{result.sql}")
            if result.answer:
                click.echo(f"\nResult: {result.answer}")
            if result.data:
                click.echo(f"\nData ({result.row_count} rows):")
                for i, row in enumerate(result.data[:5], 1):
                    click.echo(f"  {i}: {row}")
                if result.row_count > 5:
                    click.echo(f"  ... and {result.row_count - 5} more rows")
        else:
            click.echo("✗ Query failed")
            click.echo(f"Error: {result.error}")
        
        # Save result if requested
        if save_result:
            output_data = result.model_dump() if hasattr(result, 'model_dump') else result.to_dict()
            
            save_path = Path(save_result)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(save_path, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            click.echo(f"\nResult saved to: {save_result}")
        
        db_manager.close()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        if verbose or ctx.obj.get('verbose'):
            import traceback
            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option('--config', '-c', help='Configuration file path')
@click.pass_context
def test(ctx, config: Optional[str]):
    """Test database connection"""
    
    try:
        # Load database config
        if config and Path(config).exists():
            with open(config, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            db_config = DatabaseConfig(**config_data.get('database', {}))
        else:
            db_config = DatabaseConfig.from_env()
        
        click.echo("Testing database connection...")
        
        db_manager = DatabaseManager(db_config)
        if db_manager.initialize():
            click.echo("✓ Database connection successful")
            
            # Get database info
            info = db_manager.get_database_info()
            click.echo(f"Database: {info['database']}")
            click.echo(f"Type: {info['type']}")
            click.echo(f"Version: {info['version']}")
            click.echo(f"Tables: {info['tables_count']}")
        else:
            click.echo("✗ Database connection failed")
        
        db_manager.close()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--config', '-c', help='Configuration file path')
@click.option('--table', '-t', help='Specific table name')
@click.pass_context
def schema(ctx, config: Optional[str], table: Optional[str]):
    """View database schema"""
    
    try:
        # Load database config
        if config and Path(config).exists():
            with open(config, 'r', encoding='utf-8') as f:
                config_data = yaml.safe_load(f)
            db_config = DatabaseConfig(**config_data.get('database', {}))
        else:
            db_config = DatabaseConfig.from_env()
        
        db_manager = DatabaseManager(db_config)
        if not db_manager.initialize():
            click.echo("Error: Database connection failed", err=True)
            sys.exit(1)
        
        if table:
            # Show specific table info
            table_info = db_manager.get_table_info(table)
            click.echo(f"Table info: {table}")
            click.echo(json.dumps(table_info, ensure_ascii=False, indent=2))
        else:
            # Show all tables
            tables = db_manager.get_tables()
            click.echo(f"Database: {db_config.database}")
            click.echo(f"Tables ({len(tables)}):")
            
            for table_name in tables:
                click.echo(f"  - {table_name}")
        
        db_manager.close()
        
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()