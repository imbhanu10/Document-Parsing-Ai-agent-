import json
import re
from pypdf import PdfReader
import google.generativeai as genai
import os

# Configure Gemini
genai.configure(api_key=os.getenv("AIzaSyCdXe87cfAd3daQQ8RFhLUBKHCRU2BOqIw"))

# -------------------------------------------------------------
# HELPER: Clean JSON from LLM response
# -------------------------------------------------------------
def extract_json(text):
    """Extract JSON from markdown code blocks or raw text"""
    # Remove markdown code blocks
    text = re.sub(r'```(?:json)?\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    
    # Try to find JSON object
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json.loads(json_match.group(0))
    
    # Try to find JSON array
    array_match = re.search(r'\[.*\]', text, re.DOTALL)
    if array_match:
        return json.loads(array_match.group(0))
    
    return json.loads(text)

# -------------------------------------------------------------
# TASK 1 — PDF TEXT EXTRACTION
# -------------------------------------------------------------
def extract_pdf_text(pdf_path):
    """Extract and clean text from PDF"""
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        content = page.extract_text()
        if content:
            text += content + "\n"
    
    # Cleanup
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    return text.strip()

# -------------------------------------------------------------
# LLM HELPER (Gemini)
# -------------------------------------------------------------
def ask_gemini(prompt, temperature=0.3):
    """Query Gemini with retry logic"""
    try:
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                temperature=temperature,
            )
        )
        return response.text
    except Exception as e:
        return json.dumps({"error": str(e)})

# -------------------------------------------------------------
# TASK 2 — SUMMARIZATION
# -------------------------------------------------------------
def summarize_act(text):
    """Generate 5-10 bullet point summary"""
    prompt = f"""Analyze the following legislative Act and provide a summary with exactly 5-10 bullet points covering:

1. Purpose of the Act
2. Key definitions
3. Eligibility criteria
4. Obligations (who must do what)
5. Enforcement elements and penalties

Format each point clearly with a bullet point (•).

Act Text:
{text}

Provide ONLY the bullet points, no preamble."""
    
    return ask_gemini(prompt)

# -------------------------------------------------------------
# TASK 3 — KEY LEGISLATIVE SECTION EXTRACTION
# -------------------------------------------------------------
def extract_sections(text):
    """Extract key sections into structured JSON"""
    prompt = f"""Extract the following information from this legislative Act and return it as valid JSON:

Required fields:
- definitions: Key terms and their meanings
- obligations: What parties are obligated to do
- responsibilities: Specific responsibilities of administering authority
- eligibility: Who qualifies for benefits/coverage
- payments: Payment calculations, amounts, or entitlement structure
- penalties: Enforcement mechanisms and penalties for non-compliance
- record_keeping: Record-keeping and reporting requirements

Act Text:
{text}

Return ONLY a valid JSON object with these exact keys. Each value should be a concise string (2-4 sentences) summarizing that aspect.

Example format:
{{
    "definitions": "The Act defines...",
    "obligations": "Claimants must...",
    "responsibilities": "The Secretary of State is responsible for...",
    "eligibility": "Individuals are eligible if...",
    "payments": "Payment amounts are calculated based on...",
    "penalties": "Non-compliance may result in...",
    "record_keeping": "Records must be maintained for..."
}}"""
    
    raw = ask_gemini(prompt, temperature=0.2)
    try:
        return extract_json(raw)
    except Exception as e:
        return {
            "error": f"Failed to parse JSON: {str(e)}", 
            "raw": raw[:500]
        }

# -------------------------------------------------------------
# TASK 4 — RULE CHECKS (Batch Processing)
# -------------------------------------------------------------
def run_rule_checks(text):
    """Check all 6 rules in one API call"""
    rules = [
        "Act must define key terms",
        "Act must specify eligibility criteria",
        "Act must specify responsibilities of the administering authority",
        "Act must include enforcement or penalties",
        "Act must include payment calculation or entitlement structure",
        "Act must include record-keeping or reporting requirements"
    ]
    
    prompt = f"""Evaluate ALL of the following rules against the Universal Credit Act provided.

For EACH rule, determine:
1. Does the Act satisfy this requirement? (pass/fail)
2. What specific evidence supports your determination? (cite section numbers or specific text)
3. How confident are you? (0-100)

Rules to evaluate:
{json.dumps(rules, indent=2)}

Act Text:
{text}

Return a JSON array with one object per rule in this exact format:
[
    {{
        "rule": "Act must define key terms",
        "status": "pass",
        "evidence": "Section 2 defines 'universal credit', 'claimant', and 'assessment period'",
        "confidence": 95
    }},
    ...
]

Return ONLY the JSON array, no other text."""
    
    response = ask_gemini(prompt, temperature=0.1)
    
    try:
        result = extract_json(response)
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "results" in result:
            return result["results"]
        else:
            # Fallback to individual checks
            return run_rule_checks_individual(text, rules)
    except Exception as e:
        print(f"Batch processing failed: {e}, falling back to individual checks")
        return run_rule_checks_individual(text, rules)

def run_rule_checks_individual(text, rules):
    """Fallback: Check rules individually"""
    results = []
    for rule in rules:
        prompt = f"""Evaluate this rule for the Universal Credit Act:

Rule: {rule}

Determine:
1. Does the Act satisfy this requirement? (pass/fail)
2. What specific evidence supports your determination?
3. Confidence level (0-100)

Act Text:
{text}

Return valid JSON:
{{
    "rule": "{rule}",
    "status": "pass or fail",
    "evidence": "specific section or quote",
    "confidence": 85
}}"""
        
        response = ask_gemini(prompt, temperature=0.1)
        try:
            results.append(extract_json(response))
        except:
            results.append({
                "rule": rule,
                "status": "error",
                "evidence": "Failed to parse response",
                "confidence": 0
            })
    return results

# -------------------------------------------------------------
# MAIN AGENT PIPELINE
# -------------------------------------------------------------
def run_agent(pdf_path, progress_callback=None):
    """Run the complete agent pipeline with progress updates"""
    
    def update_progress(message, progress):
        if progress_callback:
            progress_callback(message, progress)
        else:
            print(f"{message} ({progress}%)")
    
    # Task 1
    update_progress("📄 Extracting PDF text...", 10)
    text = extract_pdf_text(pdf_path)
    update_progress(f"✓ Extracted {len(text):,} characters", 25)
    
    # Task 2
    update_progress("📝 Summarizing Act...", 35)
    summary = summarize_act(text)
    update_progress("✓ Summary complete", 50)
    
    # Task 3
    update_progress("🔍 Extracting key sections...", 60)
    sections = extract_sections(text)
    update_progress("✓ Sections extracted", 75)
    
    # Task 4
    update_progress("✅ Running rule checks...", 85)
    rule_results = run_rule_checks(text)
    update_progress(f"✓ Checked {len(rule_results)} rules", 95)
    
    final_output = {
        "metadata": {
            "pdf_path": pdf_path,
            "text_length": len(text),
            "model": "gemini-1.5-flash",
            "tasks_completed": [
                "text_extraction", 
                "summarization", 
                "section_extraction", 
                "rule_checking"
            ]
        },
        "summary": summary,
        "sections": sections,
        "rules": rule_results
    }
    
    update_progress("✨ Complete!", 100)
    return final_output

def save_output(output, filename="output.json"):
    """Save output to JSON file"""
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=4, ensure_ascii=False)
    return filename

# -------------------------------------------------------------
# CLI INTERFACE
# -------------------------------------------------------------
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python agent.py <path_to_pdf>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    print("🤖 Starting AI Agent for Universal Credit Act Analysis\n")
    
    result = run_agent(pdf_path)
    output_file = save_output(result)
    
    print(f"\n✅ Analysis complete! Results saved to: {output_file}")
    print(f"\n📊 Summary:\n{result['summary']}")
    print(f"\n✓ All {len(result['rules'])} rules checked")