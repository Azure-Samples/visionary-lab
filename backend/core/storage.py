import os
import uuid
import shutil
from typing import Dict, List, Optional
from fastapi import UploadFile
from pathlib import Path

from core.config import settings


class StorageService:
    """Service for handling file storage operations"""

    def __init__(self):
        """Initialize storage directories"""
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        os.makedirs(settings.IMAGE_DIR, exist_ok=True)
        os.makedirs(settings.VIDEO_DIR, exist_ok=True)
        os.makedirs(os.path.join(settings.VIDEO_DIR,
                    "generated"), exist_ok=True)

    async def save_uploaded_file(self, file: UploadFile, directory: str) -> Dict[str, str]:
        """
        Save an uploaded file to the specified directory

        Args:
            file: The uploaded file
            directory: Directory to save the file in

        Returns:
            Dictionary with file_id and file_path
        """
        # Generate a unique ID for the file
        file_id = str(uuid.uuid4())

        # Get file extension
        _, ext = os.path.splitext(file.filename)

        # Create filename with UUID
        filename = f"{file_id}{ext}"
        file_path = os.path.join(directory, filename)

        # Save the file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return {
            "file_id": file_id,
            "file_path": file_path,
            "filename": filename
        }

    def get_file_path(self, file_id: str, directory: str, extension: str = None) -> str:
        """
        Get the file path for a given file ID

        Args:
            file_id: The file ID
            directory: Directory where the file is stored
            extension: Optional file extension

        Returns:
            Full path to the file
        """
        if extension:
            filename = f"{file_id}{extension}"
        else:
            # Try to find the file by ID prefix
            for file in os.listdir(directory):
                if file.startswith(file_id):
                    filename = file
                    break
            else:
                raise FileNotFoundError(
                    f"File with ID {file_id} not found in {directory}")

        return os.path.join(directory, filename)

    def list_files(self, directory: str, limit: int = 100, offset: int = 0) -> List[Dict]:
        """
        List files in a directory

        Args:
            directory: Directory to list files from
            limit: Maximum number of files to return
            offset: Offset for pagination

        Returns:
            List of file information dictionaries
        """
        files = []

        # Get all files in the directory
        all_files = [f for f in os.listdir(
            directory) if os.path.isfile(os.path.join(directory, f))]

        # Sort by modification time (newest first)
        all_files.sort(key=lambda f: os.path.getmtime(
            os.path.join(directory, f)), reverse=True)

        # Apply pagination
        paginated_files = all_files[offset:offset + limit]

        # Get file information
        for filename in paginated_files:
            file_path = os.path.join(directory, filename)
            # Assuming filename is in the format {uuid}.{extension}
            file_id = filename.split('.')[0]

            files.append({
                "file_id": file_id,
                "filename": filename,
                "file_path": file_path,
                "size": os.path.getsize(file_path),
                "created_at": os.path.getctime(file_path),
                "modified_at": os.path.getmtime(file_path)
            })

        return files

    def delete_file(self, file_id: str, directory: str) -> bool:
        """
        Delete a file by ID

        Args:
            file_id: The file ID
            directory: Directory where the file is stored

        Returns:
            True if the file was deleted, False otherwise
        """
        try:
            file_path = self.get_file_path(file_id, directory)
            os.remove(file_path)
            return True
        except (FileNotFoundError, OSError):
            return False
