from google import genai
from dotenv import load_dotenv
import os
from agents.security_agent import run_security_agent
from agents.correctness_agent import run_correctness_agent
from agents.readability_agent import run_readability_agent
from coordinator import run_coordinator

# Load API key from .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Set up Gemini
client = genai.Client(api_key=api_key)

# Sample code to review — we'll change this later
sample_code = """
def login(username, password):
    query = "SELECT * FROM users WHERE username = '" + username + "' AND password = '" + password + "'"
    result = db.execute(query)
    if result:
        return True
    return False
"""

print("=" * 60)
print("CODE REVIEW AGENT - STARTING ANALYSIS")
print("=" * 60)

print("\n[1/4] Running Security Agent...")
security_report = run_security_agent(sample_code, client)

print("[2/4] Running Correctness Agent...")
correctness_report = run_correctness_agent(sample_code, client)

print("[3/4] Running Readability Agent...")
readability_report = run_readability_agent(sample_code, client)

print("[4/4] Coordinator synthesizing final report...")
final_report = run_coordinator(sample_code, security_report, correctness_report, readability_report, client)

print("\n" + "=" * 60)
print("FINAL REPORT")
print("=" * 60)
print(final_report)