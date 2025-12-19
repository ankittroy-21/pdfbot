"""
Async File Handler Module
Non-blocking file operations for improved performance
"""

import aiofiles
import aiofiles.os
import os
from typing import Optional, List
from pathlib import Path


class AsyncFileHandler:
    """
    Async file operations manager for non-blocking I/O.
    
    Features:
    - Async read/write operations
    - Streaming file processing
    - Proper resource cleanup
    - Memory-efficient chunk processing
    """
    
    @staticmethod
    async def read_file(file_path: str, mode: str = 'rb') -> Optional[bytes]:
        """
        Async file read operation.
        
        Args:
            file_path: Path to file
            mode: File open mode (default: 'rb' for binary read)
            
        Returns:
            File contents as bytes, or None on error
        """
        try:
            async with aiofiles.open(file_path, mode) as f:  # type: ignore
                content = await f.read()
            return content
        except Exception as e:
            print(f"❌ Failed to read file {file_path}: {e}")
            return None
    
    @staticmethod
    async def write_file(file_path: str, content: bytes, mode: str = 'wb') -> bool:
        """
        Async file write operation.
        
        Args:
            file_path: Path to file
            content: Content to write
            mode: File open mode (default: 'wb' for binary write)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Ensure directory exists
            directory = os.path.dirname(file_path)
            if directory and not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
            
            async with aiofiles.open(file_path, mode) as f:  # type: ignore
                await f.write(content)
            return True
        except Exception as e:
            print(f"❌ Failed to write file {file_path}: {e}")
            return False
    
    @staticmethod
    async def delete_file(file_path: str) -> bool:
        """
        Async file deletion with error handling.
        
        Args:
            file_path: Path to file to delete
            
        Returns:
            True if deleted, False otherwise
        """
        try:
            if os.path.exists(file_path):
                await aiofiles.os.remove(file_path)
                print(f"✅ Deleted: {file_path}")
                return True
            return False
        except Exception as e:
            print(f"⚠️ Failed to delete {file_path}: {e}")
            return False
    
    @staticmethod
    async def delete_files(file_paths: List[str]) -> int:
        """
        Delete multiple files asynchronously.
        
        Args:
            file_paths: List of file paths to delete
            
        Returns:
            Number of files successfully deleted
        """
        deleted_count = 0
        for file_path in file_paths:
            if await AsyncFileHandler.delete_file(file_path):
                deleted_count += 1
        return deleted_count
    
    @staticmethod
    async def cleanup_directory(directory: str, pattern: str = "*") -> int:
        """
        Clean up files in directory matching pattern.
        
        Args:
            directory: Directory path
            pattern: File pattern (default: "*" for all files)
            
        Returns:
            Number of files deleted
        """
        try:
            if not os.path.exists(directory):
                return 0
            
            path = Path(directory)
            files_to_delete = list(path.glob(pattern))
            
            deleted_count = 0
            for file_path in files_to_delete:
                if file_path.is_file():
                    try:
                        await aiofiles.os.remove(str(file_path))
                        deleted_count += 1
                    except Exception as e:
                        print(f"⚠️ Failed to delete {file_path}: {e}")
            
            if deleted_count > 0:
                print(f"🧹 Cleaned up {deleted_count} files from {directory}")
            
            return deleted_count
        except Exception as e:
            print(f"⚠️ Cleanup failed for {directory}: {e}")
            return 0
    
    @staticmethod
    async def file_exists(file_path: str) -> bool:
        """
        Check if file exists asynchronously.
        
        Args:
            file_path: Path to check
            
        Returns:
            True if file exists
        """
        # os.path.exists is fast enough, no need for async
        return os.path.exists(file_path)
    
    @staticmethod
    async def get_file_size(file_path: str) -> int:
        """
        Get file size asynchronously.
        
        Args:
            file_path: Path to file
            
        Returns:
            File size in bytes, or 0 on error
        """
        try:
            stat = await aiofiles.os.stat(file_path)
            return stat.st_size
        except:
            try:
                # Fallback to synchronous stat
                return os.path.getsize(file_path)
            except:
                return 0
