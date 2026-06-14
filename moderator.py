import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

# Instagram reporting categories mapping
INSTAGRAM_REPORT_MAPPING = {
    "hate": "Hate Speech or Symbols",
    "harassment": "Harassment or Bullying",
    "self-harm": "Self-Injury",
    "sexual": "Sexual Content",
    "violence": "Violence or Threats",
    "illegal": "Illegal Activities",
    "spam": "Spam or Scams"
}

def check_content_policy(text):
    results = {"is_safe": True, "violations": [], "suggested_reports": []}
    if not text: return results
    try:
        response = client.moderations.create(input=text)
        output = response.results[0]
        if output.flagged:
            results["is_safe"] = False
            categories = output.categories.to_dict()
            for cat, flagged in categories.items():
                if flagged:
                    results["violations"].append(cat)
                    # Mapping to Instagram categories
                    for key, val in INSTAGRAM_REPORT_MAPPING.items():
                        if key in cat: results["suggested_reports"].append(val)
    except: pass
    return results
  
