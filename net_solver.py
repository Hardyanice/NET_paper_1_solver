import streamlit as st
import google.generativeai as genai
from pdf2image import convert_from_bytes
import json
import os
from dotenv import load_dotenv

load_dotenv()

# ----------------------------
# CONFIG
# ----------------------------

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    st.error("Set GEMINI_API_KEY environment variable.")
    st.stop()

genai.configure(api_key=API_KEY)

# Extraction model 
extract_model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config={
        "temperature": 0,
        "top_p": 0.1
    }
)

# Separate reasoning model
reason_model = genai.GenerativeModel(
    "gemini-3-flash-preview",
    generation_config={
        "temperature": 0,
        "top_p": 0.1
    }
)

st.set_page_config(layout="wide")
st.title("UGC NET Paper 1 – Mini Test")

uploaded_pdf = st.file_uploader("Upload UGC NET Paper PDF", type=["pdf"])


# ----------------------------
# EXTRACTION LOGIC
# ----------------------------

def extract_with_gemini(pages):
    prompt = """
You are given images of a UGC NET Paper 1 question paper.

Extract ONLY English MCQs.
Ignore Hindi.
Ignore instructions.
Ignore metadata.
Ignore page headers.

IMPORTANT:
If a question contains a TABLE, DATA, PASSAGE, CHART, or any structured content,
you MUST include the FULL table text exactly as visible.
Do NOT summarize.
Do NOT omit numeric values.
Do NOT simplify tables.
Preserve all numbers, percentages, and rows.

Return STRICT JSON in this format:

{
  "1": {
    "question": "FULL question text including table if present",
    "options": {
      "1": "...",
      "2": "...",
      "3": "...",
      "4": "..."
    }
  }
}

Extract all 50 questions if present.

Return ONLY raw JSON.
Do NOT wrap in markdown.
Do NOT add explanations.
Do NOT add markdown.
"""

    response = extract_model.generate_content([prompt] + pages)
    return response.text


def clean_json_response(text):
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 2:
            text = parts[1]
    text = text.replace("json", "").strip()
    return text


# ----------------------------
# REASONING FUNCTION
# ----------------------------

def solve_with_reason_model(mcqs_subset, user_answers):
    prompt = f"""
You are evaluating a UGC NET Paper 1 test.

For each question:
1. Determine the correct option.
2. Compare it with the user's selected option.
3. If wrong, provide a brief explanation (1–2 lines).

Return ONLY JSON in this format:

{{
  "1": {{
    "correct_option": "4",
    "user_option": "2",
    "is_correct": false,
    "explanation": "Short explanation here."
  }},
  "2": {{
    "correct_option": "3",
    "user_option": "3",
    "is_correct": true,
    "explanation": ""
  }}
}}

Questions:
{json.dumps(mcqs_subset, indent=2)}

User Answers:
{json.dumps(user_answers, indent=2)}

Return ONLY raw JSON.
Do NOT wrap in markdown.
Do NOT add commentary.
"""

    response = reason_model.generate_content(prompt)
    return json.loads(clean_json_response(response.text))


# ----------------------------
# SESSION STATE
# ----------------------------

if "mcqs" not in st.session_state:
    st.session_state.mcqs = None


# ----------------------------
# EXTRACTION BUTTON
# ----------------------------

if st.button("Extract Questions"):

    if not uploaded_pdf:
        st.warning("Upload a PDF first.")
        st.stop()

    pages = convert_from_bytes(uploaded_pdf.read(), dpi=200)

    status = st.empty()
    status.info("Extracting questions... Please wait.")

    raw_output = extract_with_gemini(pages)
    cleaned_output = clean_json_response(raw_output)

    

    try:
        mcqs = json.loads(cleaned_output)

        # If Gemini returns list, convert to dict
        if isinstance(mcqs, list):
            mcqs = {str(i+1): q for i, q in enumerate(mcqs)}

        st.session_state.mcqs = mcqs
        st.success(f"Extracted {len(mcqs)} questions.")

        with st.expander("View Extracted Questions (JSON)"):
            st.json(mcqs)

    except Exception as e:
        st.error("Extraction failed.")
        st.text(raw_output)
        st.text(f"Error: {e}")


# ----------------------------
# TEST FORM 
# ----------------------------

if st.session_state.mcqs:

    mcqs = st.session_state.mcqs
    first_fifty = dict(list(mcqs.items())[:50])

    st.markdown("### Select your answers:")

    user_answers = {}

    for q_num, data in first_fifty.items():
        options = data["options"]

        choice = st.radio(
            label=f"Q{q_num}",
            options=list(options.keys()),
            format_func=lambda x: f"{x}. {options[x]}",
            key=f"q_{q_num}"
        )

        user_answers[q_num] = choice

    if st.button("Submit Test"):

        correct_answers = solve_with_reason_model(first_fifty, user_answers)

        score = 0

        st.markdown("## Results")

        for q_num in first_fifty.keys():

            result = correct_answers.get(str(q_num)) or correct_answers.get(int(q_num))

            if not result:
                st.error(f"Q{q_num}: Evaluation missing.")
                continue

            correct_opt = result.get("correct_option")
            user_opt = user_answers[q_num]
            explanation = result.get("explanation", "")

            if user_opt == correct_opt:
                score += 1
                st.success(f"Q{q_num}: Correct (Option {correct_opt})")
            else:
                st.error(f"Q{q_num}: Wrong")
                st.write(f"Your Answer: {user_opt}")
                st.write(f"Correct Answer: {correct_opt}")

                if explanation:
                    st.info(f"Explanation: {explanation}")


        st.markdown(f"## Final Score: {score} / {len(first_fifty)}")
