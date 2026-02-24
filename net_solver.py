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

extract_model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config={"temperature": 0, "top_p": 0.1}
)

reason_model = genai.GenerativeModel(
    "gemini-3-flash-preview",
    generation_config={"temperature": 0, "top_p": 0.1}
)

st.set_page_config(layout="wide")
st.title("UGC NET Paper 1 – Mini Test")

uploaded_pdf = st.file_uploader("Upload UGC NET Paper PDF", type=["pdf"])


# ----------------------------
# EXTRACTION LOGIC
# ----------------------------

def extract_with_gemini(pages):
    prompt = """
Extract ONLY English MCQs from the given UGC NET Paper.

If a question contains a TABLE, preserve it fully.
Do not summarize.
Return STRICT JSON:

{
  "1": {
    "question": "...",
    "options": {
      "1": "...",
      "2": "...",
      "3": "...",
      "4": "..."
    }
  }
}

Return raw JSON only.
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
Evaluate these MCQs.

Return ONLY JSON in this format:

{{
  "1": {{
    "correct_option": "4",
    "user_option": "2",
    "is_correct": false,
    "explanation": "Short explanation"
  }}
}}

Questions:
{json.dumps(mcqs_subset)}

User Answers:
{json.dumps(user_answers)}

Return raw JSON only.
"""

    try:
        response = reason_model.generate_content(prompt)
        raw_text = response.text.strip()
    except Exception:
        return {}

    cleaned = clean_json_response(raw_text)

    try:
        return json.loads(cleaned)
    except Exception:
        try:
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            return json.loads(cleaned[start:end])
        except Exception:
            return {}


# ----------------------------
# BATCH EVALUATION (NEW)
# ----------------------------

def solve_in_batches(mcqs, user_answers, batch_size=10):
    all_results = {}
    items = list(mcqs.items())

    for i in range(0, len(items), batch_size):

        batch_raw = dict(items[i:i+batch_size])

        # Compress question text to reduce token size
        batch = {}
        for k, v in batch_raw.items():
            compressed_question = " ".join(
                v.get("question", "").split()
            )  # removes extra whitespace + newlines

            batch[k] = {
                "question": compressed_question,
                "options": v.get("options", {})
            }

        batch_user = {k: user_answers[k] for k in batch.keys()}

        batch_result = solve_with_reason_model(batch, batch_user)

        if not batch_result:
            return {}

        all_results.update(batch_result)

    return all_results


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

    raw_output = extract_with_gemini(pages)
    cleaned_output = clean_json_response(raw_output)

    try:
        mcqs = json.loads(cleaned_output)

        if isinstance(mcqs, list):
            mcqs = {str(i+1): q for i, q in enumerate(mcqs)}

        st.session_state.mcqs = mcqs
        st.success(f"Extracted {len(mcqs)} questions.")

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

        question_text = data.get("question", "")
        options = data.get("options", {})

        st.markdown("---")
        st.markdown(f"### Q{q_num}")
        st.markdown(question_text)

        choice = st.radio(
            label="Select your answer:",
            options=list(options.keys()),
            format_func=lambda x: f"{x}. {options[x]}",
            key=f"q_{q_num}"
        )

        user_answers[q_num] = choice


    if st.button("Submit Test"):

        with st.spinner("Evaluating answers in batches..."):
            correct_answers = solve_in_batches(first_fifty, user_answers, batch_size=10)

        if not correct_answers:
            st.error("Evaluation failed. Please try again.")
            st.stop()

        score = 0
        st.markdown("## Results")

        for q_num in first_fifty.keys():

            result = correct_answers.get(str(q_num)) or correct_answers.get(int(q_num))

            if not result:
                st.error(f"Q{q_num}: Missing evaluation.")
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

