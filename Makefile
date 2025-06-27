.PHONY: help install run clean activate

# Default target
help:
	@echo "Available commands:"
	@echo "  make install    - Install dependencies from requirements.txt"
	@echo "  make activate   - Activate virtual environment"
	@echo "  make run        - Run the Streamlit app (1_home.py)"
	@echo "  make clean      - Remove virtual environment and cache files"
	@echo "  make help       - Show this help message"

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt

# Activate virtual environment (for reference)
activate:
	@echo "To activate virtual environment, run:"
	@echo "source venv/bin/activate"

# Run the Streamlit app
run:
	@echo "Starting Streamlit app..."
	streamlit run 1_home.py

# Clean up
clean:
	@echo "Cleaning up..."
	rm -rf venv/
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 