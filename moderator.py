import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI()

INSTAGRAM_REPORT_MAPPING = {
    "hate": "Hate Speech",
    "harassment": "Harassment",
    "self-harm": "Self-Injury",
    "sexual": "Nudity or Sexual Activity",
    "violence": "Violence or Dangerous Organizations",
    "illegal": "Sale of Illegal or Regulated Goods",
    "spam": "Spam"
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
                    results["violations"].append(cat.replace('/', ' '))
                    for key, val in INSTAGRAM_REPORT_MAPPING.items():
                        if key in cat: results["suggested_reports"].append(val)
    except: pass
    return results
    
