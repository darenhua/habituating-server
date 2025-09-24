#!/bin/bash
set -e

echo "🚀 Setting up Sprint Learning workspace..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ Error: 'uv' is not installed."
    echo "Please install uv first: https://docs.astral.sh/uv/getting-started/installation/"
    exit 1
fi

# Check if .env exists in root
if [ ! -f "$CONDUCTOR_ROOT_PATH/.env" ]; then
    echo "⚠️  Warning: .env file not found in root repository."
    echo "You may need to create one with your SUPABASE_URL and SUPABASE_KEY."
fi

# Copy .env file if it exists in root
if [ -f "$CONDUCTOR_ROOT_PATH/.env" ]; then
    cp "$CONDUCTOR_ROOT_PATH/.env" .env
    echo "✅ Copied .env file from root"
else
    echo "⚠️  Skipping .env copy (not found in root)"
fi

# Install Python dependencies using uv
echo "📦 Installing Python dependencies..."
uv sync

# Install Playwright browsers if not already installed
echo "🌐 Installing Playwright browsers..."
uv run playwright install chromium || echo "⚠️  Playwright browser installation failed (may already be installed)"

echo "✨ Workspace setup complete!"
echo ""
echo "To run the FastAPI server, click the Run button or use: uvicorn main:app --reload"