# 1. Run the generator script to assemble the project directory
python setup_project.py

# 2. Enter the new directory
cd polymarket_btc_5m_bot

# 3. Create virtual environment & install dependencies
python -m venv venv
source venv/bin/activate  # Windows users: venv\Scripts\activate
pip install -r requirements.txt

# 4. Copy environmental file template
cp .env.example .env

# 5. Run the bot in DRY_RUN mode
python main.py