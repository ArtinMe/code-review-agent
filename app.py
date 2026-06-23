from flask import Flask, render_template, request
from markupsafe import Markup
from google import genai
from dotenv import load_dotenv
import os
import markdown
import time
from agents.security_agent import run_security_agent
from agents.correctness_agent import run_correctness_agent
from agents.readability_agent import run_readability_agent
from agents.performance_agent import run_performance_agent
from coordinator import run_coordinator

# Load API key
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Set up Gemini
client = genai.Client(api_key=api_key)

# Set up Flask
app = Flask(__name__)

def md(text):
    return Markup(markdown.markdown(text, extensions=['fenced_code']))

def call_with_retry(func, *args, retries=3, delay=10):
    for i in range(retries):
        try:
            return func(*args)
        except Exception as e:
            if '503' in str(e) and i < retries - 1:
                print(f"503 error, retrying in {delay} seconds... (attempt {i+1}/{retries})")
                time.sleep(delay)
            else:
                raise e

@app.route("/", methods=["GET", "POST"])
def index():
    final_report = None
    fixed_code = None
    security_report = None
    correctness_report = None
    readability_report = None
    performance_report = None
    code = None
    mode = "simple"
    error = None

    if request.method == "POST":
        code = request.form.get("code")
        mode = request.form.get("mode", "simple")

        if code:
            try:
                security_report = md(call_with_retry(run_security_agent, code, client, mode))
                correctness_report = md(call_with_retry(run_correctness_agent, code, client, mode))
                readability_report = md(call_with_retry(run_readability_agent, code, client, mode))
                performance_report = md(call_with_retry(run_performance_agent, code, client, mode))

                raw_final = call_with_retry(run_coordinator, code, security_report, correctness_report, readability_report, client)

                marker = '## Fixed Code'
                idx = raw_final.find(marker)
                if idx != -1:
                    final_report = md(raw_final[:idx].strip())
                    fixed_code = md(raw_final[idx + len(marker):].strip())
                else:
                    final_report = md(raw_final)
                    fixed_code = None

            except Exception as e:
                error = str(e)

    return render_template("index.html",
                           final_report=final_report,
                           fixed_code=fixed_code,
                           security_report=security_report,
                           correctness_report=correctness_report,
                           readability_report=readability_report,
                           performance_report=performance_report,
                           code=code,
                           mode=mode,
                           error=error)

if __name__ == "__main__":
    app.run(debug=True)