#!/usr/bin/env python3
"""Test the SWE-bench tools locally without API calls."""

import asyncio
import tempfile
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.swebench_tools import BashTool, StrReplaceEditorTool


async def test_bash_tool():
    """Test persistent bash tool."""
    print("\n=== Testing BashTool ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        (workspace / "test.py").write_text("print('hello')\n")
        
        bash = BashTool(workspace)
        
        # Test basic command
        result = await bash.execute(command="pwd")
        print(f"pwd: {result.output}")
        assert result.success
        assert str(workspace) in result.output
        
        # Test ls
        result = await bash.execute(command="ls -la")
        print(f"ls: {result.output[:100]}...")
        assert result.success
        assert "test.py" in result.output
        
        # Test cd persistence
        (workspace / "subdir").mkdir()
        result = await bash.execute(command="cd subdir")
        assert result.success
        
        result = await bash.execute(command="pwd")
        print(f"pwd after cd: {result.output}")
        assert "subdir" in result.output
        
        # Test command with error
        result = await bash.execute(command="cat nonexistent.txt")
        assert not result.success
        print(f"Error test: {result.error}")
        
        print("BashTool: All tests passed!")


async def test_str_replace_editor():
    """Test string replacement editor."""
    print("\n=== Testing StrReplaceEditorTool ===")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        
        editor = StrReplaceEditorTool(workspace)
        
        # Test create
        result = await editor.execute(
            command="create",
            path="test.py",
            file_text="def hello():\n    print('hello')\n"
        )
        print(f"create: {result.output}")
        assert result.success
        
        # Test view
        result = await editor.execute(command="view", path="test.py")
        print(f"view:\n{result.output}")
        assert result.success
        assert "hello" in result.output
        
        # Test str_replace
        result = await editor.execute(
            command="str_replace",
            path="test.py",
            old_str="print('hello')",
            new_str="print('world')"
        )
        print(f"str_replace: {result.output}")
        assert result.success
        
        # Verify replacement
        result = await editor.execute(command="view", path="test.py")
        print(f"After replace:\n{result.output}")
        assert "world" in result.output
        # 'hello' still appears in function name, but print should be 'world'
        assert "print('world')" in result.output
        
        # Test insert
        result = await editor.execute(
            command="insert",
            path="test.py",
            insert_line=1,
            new_str_for_insert="    # This is a comment\n"
        )
        print(f"insert: {result.output}")
        assert result.success
        
        # Test view with range
        result = await editor.execute(
            command="view",
            path="test.py",
            view_range=[1, 2]
        )
        print(f"view_range:\n{result.output}")
        assert result.success
        
        # Test error: str_replace with non-existent string
        result = await editor.execute(
            command="str_replace",
            path="test.py",
            old_str="this does not exist",
            new_str="replacement"
        )
        assert not result.success
        print(f"Error test: {result.error[:50]}...")
        
        # Test error: create existing file
        result = await editor.execute(
            command="create",
            path="test.py",
            file_text="new content"
        )
        assert not result.success
        print(f"Error test (exists): {result.error}")
        
        print("StrReplaceEditorTool: All tests passed!")


async def main():
    print("Testing SWE-bench tools...")
    await test_bash_tool()
    await test_str_replace_editor()
    print("\n=== All tests passed! ===")


if __name__ == "__main__":
    asyncio.run(main())
