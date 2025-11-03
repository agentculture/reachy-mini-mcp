"""
Test script to verify the tools repository structure.
"""

import json
from pathlib import Path

TOOLS_REPOSITORY_PATH = Path(__file__).parent / "tools_repository"


def test_load_tool_index():
    """Test loading the tool index."""
    index_path = TOOLS_REPOSITORY_PATH / "tools_index.json"
    
    if not index_path.exists():
        print(f"✗ Tool index not found at {index_path}")
        return False
    
    with open(index_path, 'r') as f:
        index = json.load(f)
    
    print(f"✓ Loaded tool index with {len(index.get('tools', []))} tools")
    return True


def test_load_tool_definitions():
    """Test loading all tool definitions."""
    index_path = TOOLS_REPOSITORY_PATH / "tools_index.json"
    
    with open(index_path, 'r') as f:
        index = json.load(f)
    
    errors = []
    success_count = 0
    
    for tool_entry in index.get("tools", []):
        tool_name = tool_entry.get("name")
        definition_file = tool_entry.get("definition_file")
        
        def_path = TOOLS_REPOSITORY_PATH / definition_file
        
        if not def_path.exists():
            errors.append(f"✗ Definition file not found for {tool_name}: {definition_file}")
            continue
        
        try:
            with open(def_path, 'r') as f:
                tool_def = json.load(f)
            
            # Validate structure
            if "name" not in tool_def:
                errors.append(f"✗ Tool {tool_name} missing 'name' field")
                continue
            
            if "description" not in tool_def:
                errors.append(f"✗ Tool {tool_name} missing 'description' field")
                continue
            
            if "execution" not in tool_def:
                errors.append(f"✗ Tool {tool_name} missing 'execution' field")
                continue
            
            exec_type = tool_def["execution"].get("type")
            
            if exec_type == "inline":
                if "code" not in tool_def["execution"]:
                    errors.append(f"✗ Tool {tool_name} has inline type but no code")
                    continue
            
            elif exec_type == "script":
                script_file = tool_def["execution"].get("script_file")
                if not script_file:
                    errors.append(f"✗ Tool {tool_name} has script type but no script_file")
                    continue
                
                script_path = TOOLS_REPOSITORY_PATH / "scripts" / script_file
                if not script_path.exists():
                    errors.append(f"✗ Script file not found for {tool_name}: {script_file}")
                    continue
            
            print(f"✓ Tool definition valid: {tool_name} ({exec_type})")
            success_count += 1
            
        except json.JSONDecodeError as e:
            errors.append(f"✗ Invalid JSON in {definition_file}: {e}")
        except Exception as e:
            errors.append(f"✗ Error loading {tool_name}: {e}")
    
    print(f"\n{'='*60}")
    print(f"Results: {success_count} valid, {len(errors)} errors")
    print(f"{'='*60}")
    
    if errors:
        print("\nErrors:")
        for error in errors:
            print(error)
        return False
    
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("Testing Reachy Mini Tools Repository")
    print("="*60)
    print(f"Repository path: {TOOLS_REPOSITORY_PATH}\n")
    
    if not test_load_tool_index():
        print("\n✗ Tool index test failed!")
        return
    
    print()
    
    if not test_load_tool_definitions():
        print("\n✗ Tool definitions test failed!")
        return
    
    print("\n✓ All tests passed! Repository structure is valid.")


if __name__ == "__main__":
    main()


