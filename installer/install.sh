#!/bin/bash
set -e

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo ""
echo -e "${BLUE} ================================================${NC}"
echo -e "${BLUE}   StockFlow Installer for Mac / Linux${NC}"
echo -e "${BLUE} ================================================${NC}"
echo ""

# ── Detect OS ─────────────────────────────────────────────────────────────────
OS="linux"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="mac"
fi

# ── Detect update vs fresh install ───────────────────────────────────────────
INSTALL_DIR="$HOME/StockFlow"
IS_UPDATE=false
if [ -f "$INSTALL_DIR/.env" ]; then
    IS_UPDATE=true
    echo -e "${YELLOW} [INFO] Existing installation detected. Running UPDATE...${NC}"
else
    echo -e "${GREEN} [INFO] No existing installation. Running FRESH INSTALL...${NC}"
fi

# ── Check internet ────────────────────────────────────────────────────────────
echo ""
echo " [1/6] Checking internet connection..."
if ! ping -c 1 github.com &>/dev/null; then
    echo -e "${RED} [ERROR] No internet connection. Please connect and try again.${NC}"
    exit 1
fi
echo -e "${GREEN} [OK] Internet available.${NC}"

# ── Check/Install Python ──────────────────────────────────────────────────────
echo ""
echo " [2/6] Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo " [INFO] Python not found. Installing..."
    if [ "$OS" == "mac" ]; then
        if ! command -v brew &>/dev/null; then
            echo " [INFO] Installing Homebrew first..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        brew install python@3.11
    else
        sudo apt-get update -qq
        sudo apt-get install -y python3 python3-pip python3-venv
    fi
    echo -e "${GREEN} [OK] Python installed.${NC}"
else
    echo -e "${GREEN} [OK] Python already installed.${NC}"
fi

# ── Check/Install MongoDB ─────────────────────────────────────────────────────
echo ""
echo " [3/6] Checking MongoDB..."
if ! command -v mongod &>/dev/null; then
    echo " [INFO] MongoDB not found. Installing..."
    if [ "$OS" == "mac" ]; then
        brew tap mongodb/brew
        brew install mongodb-community@7.0
    else
        # Ubuntu/Debian
        curl -fsSL https://www.mongodb.org/static/pgp/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
        echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg ] https://repo.mongodb.org/apt/ubuntu jammy/mongodb-org/7.0 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
        sudo apt-get update -qq
        sudo apt-get install -y mongodb-org
    fi
    echo -e "${GREEN} [OK] MongoDB installed.${NC}"
else
    echo -e "${GREEN} [OK] MongoDB already installed.${NC}"
fi

# Create data directory
mkdir -p "$HOME/StockFlow-data/db"

# ── Clone or update StockFlow ─────────────────────────────────────────────────
echo ""
echo " [4/6] Getting StockFlow code..."
if [ "$IS_UPDATE" = true ]; then
    echo " [INFO] Pulling latest updates..."
    cd "$INSTALL_DIR"
    git pull origin main
    echo -e "${GREEN} [OK] Updated.${NC}"
else
    echo " [INFO] Cloning from GitHub..."
    git clone https://github.com/VINN5/StockFlow.git "$INSTALL_DIR"
    echo -e "${GREEN} [OK] Downloaded.${NC}"
fi

# ── Install Python dependencies ───────────────────────────────────────────────
echo ""
echo " [5/6] Installing dependencies..."
cd "$INSTALL_DIR"
pip3 install --upgrade pip --quiet
pip3 install -r requirements.txt --quiet
echo -e "${GREEN} [OK] Dependencies installed.${NC}"

# ── Create .env (fresh install only) ─────────────────────────────────────────
if [ "$IS_UPDATE" = false ]; then
    echo ""
    echo " [6/6] Creating configuration..."
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > "$INSTALL_DIR/.env" <<EOF
SECRET_KEY=$SECRET_KEY
MONGODB_URI=mongodb://localhost:27017/stockflow
MPESA_ENV=sandbox
AT_USERNAME=sandbox
EOF
    echo -e "${GREEN} [OK] Configuration created.${NC}"
else
    echo ""
    echo " [6/6] Keeping existing configuration."
    echo -e "${GREEN} [OK] .env preserved.${NC}"
fi

# ── Seed sample data (fresh install only) ─────────────────────────────────────
if [ "$IS_UPDATE" = false ]; then
    echo ""
    echo " [INFO] Seeding sample data..."
    if [ "$OS" == "mac" ]; then
        brew services start mongodb-community@7.0
    else
        sudo systemctl start mongod
    fi
    sleep 3
    python3 "$INSTALL_DIR/installer/seed.py"
    echo -e "${GREEN} [OK] Sample data loaded.${NC}"
fi

# ── Create startup script ─────────────────────────────────────────────────────
STARTUP="$HOME/Desktop/StockFlow.command"
# Fallback if no Desktop
[ ! -d "$HOME/Desktop" ] && STARTUP="$HOME/StockFlow.command"

cat > "$STARTUP" <<EOF
#!/bin/bash
echo "Starting StockFlow..."

# Start MongoDB
if [[ "\$OSTYPE" == "darwin"* ]]; then
    brew services start mongodb-community@7.0 2>/dev/null || true
else
    sudo systemctl start mongod 2>/dev/null || mongod --dbpath \$HOME/StockFlow-data/db --fork --logpath \$HOME/StockFlow-data/mongod.log
fi

sleep 2

# Open browser
if [[ "\$OSTYPE" == "darwin"* ]]; then
    open "http://localhost:5000"
else
    xdg-open "http://localhost:5000" 2>/dev/null || true
fi

# Start Flask
cd "$INSTALL_DIR"
python3 -m backend.app
EOF

chmod +x "$STARTUP"

echo ""
echo -e "${GREEN} ================================================${NC}"
if [ "$IS_UPDATE" = true ]; then
    echo -e "${GREEN}   StockFlow updated successfully!${NC}"
else
    echo -e "${GREEN}   StockFlow installed successfully!${NC}"
fi
echo -e "${GREEN} ================================================${NC}"
echo ""
echo "  Startup script created at: $STARTUP"
echo "  Double-click it to launch StockFlow."
echo "  StockFlow opens at: http://localhost:5000"
echo ""

# Ask to launch now
read -p " Launch StockFlow now? (y/n): " LAUNCH
if [[ "$LAUNCH" == "y" || "$LAUNCH" == "Y" ]]; then
    bash "$STARTUP"
fi