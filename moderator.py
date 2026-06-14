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
    results = {"is_safe": True, "violations": [], "suggested_reports": [], "top_risks": []}
    if not text: return results
    try:
        response = client.moderations.create(input=text)
        output = response.results[0]
        scores = output.category_scores.to_dict()
        sorted_risks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        for cat, score in sorted_risks[:3]:
            results["top_risks"].append({"category": cat.replace('/', ' ').title(), "chance": round(score * 100, 2)})
        if output.flagged:
            results["is_safe"] = False
            for cat, flagged in output.categories.to_dict().items():
                if flagged:
                    results["violations"].append(cat.replace('/', ' '))
                    for key, val in INSTAGRAM_REPORT_MAPPING.items():
                        if key in cat: results["suggested_reports"].append(val)
    except: pass
    return results
    
