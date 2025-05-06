#!/bin/bash

# Display welcome message
echo "===========================================" 
echo "Visionary Lab Setup Script"
echo "===========================================" 

# Determine the repository root directory
# For local testing
if [ -d "/Users/ali/Dev/ip/visionary-lab" ]; then
  REPO_ROOT="/Users/ali/Dev/ip/visionary-lab"
# For GitHub Codespaces
elif [ -d "/workspaces/visionary-lab" ]; then
  REPO_ROOT="/workspaces/visionary-lab"
# Try to find it relative to current directory
else
  # Get the directory where the script is located
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  # Get the parent directory (repo root)
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

# Reminder to edit the .env file
BACKEND_ENV_PATH="$REPO_ROOT/backend/.env"
echo ""
echo "IMPORTANT: Before running the application, you need to update your backend environment file:"
echo "Edit: $BACKEND_ENV_PATH"
echo "Replace the following placeholders with your actual Azure credentials:"
echo "  - AOAI_RESOURCE"
echo "  - AOAI_API_KEY"
echo "  - AOAI_API_VERSION"
echo "  - IMAGEGEN_DEPLOYMENT"
echo "  - IMAGEGEN_AOAI_API_KEY"
echo "  - AZURE_STORAGE_ACCOUNT"
echo "  - AZURE_STORAGE_KEY"
echo "  - AZURE_CONTAINER_NAME"
echo ""
echo "Would you like to open the .env file now? (y/n)"
read open_env

if [[ "$open_env" == "y" || "$open_env" == "Y" ]]; then
  if command -v code &> /dev/null; then
    code "$BACKEND_ENV_PATH"
  else
    echo "VS Code not found. Please open the file manually: $BACKEND_ENV_PATH"
  fi
fi

# Check if next.config.ts exists
NEXT_CONFIG_PATH="$REPO_ROOT/frontend/next.config.ts"
if [ ! -f "$NEXT_CONFIG_PATH" ]; then
  echo "Error: next.config.ts not found at $NEXT_CONFIG_PATH"
  echo "Please make sure you have the correct repository structure."
  exit 1
fi

# Ask for Azure storage account name
echo ""
echo "Please enter your Azure storage account name:"
read storage_account_name

# Check if input is not empty
if [ -z "$storage_account_name" ]; then
  echo "No storage account name provided. You can manually update next.config.ts later."
else
  echo "Updating next.config.ts with storage account name: $storage_account_name"
  
  # Update next.config.ts with the storage account name
  # Using sed to replace the placeholder in the hostname field
  if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS requires an empty string for -i
    sed -i '' "s/<storage-account-name>/$storage_account_name/g" "$NEXT_CONFIG_PATH"
  else
    # Linux
    sed -i "s/<storage-account-name>/$storage_account_name/g" "$NEXT_CONFIG_PATH"
  fi
  
  # Verify the update
  if grep -q "$storage_account_name" "$NEXT_CONFIG_PATH"; then
    echo "next.config.ts has been updated successfully!"
  else
    echo "Warning: Failed to update next.config.ts. You may need to manually update it."
  fi
fi

echo ""
echo "Setup complete! To start the application:"
echo "1. Remember to update your Azure credentials in backend/.env"
echo "2. Backend: cd backend && uv run fastapi dev"
echo "3. Frontend: cd frontend && npm run dev"
echo "===========================================" 
