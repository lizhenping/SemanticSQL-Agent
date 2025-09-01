"""Check LangChain version and imports"""
try:
    import langchain
    print(f"langchain version: {langchain.__version__}")
    
    # Try different import paths
    print("\nTrying imports:")
    
    try:
        from langchain.memory import BaseMemory
        print("✓ from langchain.memory import BaseMemory")
    except ImportError as e:
        print(f"✗ from langchain.memory import BaseMemory - {e}")
    
    try:
        from langchain.memory.base import BaseMemory
        print("✓ from langchain.memory.base import BaseMemory")
    except ImportError as e:
        print(f"✗ from langchain.memory.base import BaseMemory - {e}")
    
    try:
        from langchain_core.memory import BaseMemory
        print("✓ from langchain_core.memory import BaseMemory")
    except ImportError as e:
        print(f"✗ from langchain_core.memory import BaseMemory - {e}")
    
    try:
        from langchain.schema.memory import BaseMemory
        print("✓ from langchain.schema.memory import BaseMemory")
    except ImportError as e:
        print(f"✗ from langchain.schema.memory import BaseMemory - {e}")
        
    # Check available memory classes
    print("\nAvailable in langchain.memory:")
    import langchain.memory
    print([attr for attr in dir(langchain.memory) if not attr.startswith('_')])
    
except Exception as e:
    print(f"Error: {e}")