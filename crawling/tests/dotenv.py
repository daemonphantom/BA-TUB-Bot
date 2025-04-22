from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Access variables
username = os.getenv("TUB_USERNAME")
password = os.getenv("TUB_PASSWORD")

print(f"Username: {username}")
print(f"Password: {password}")
