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

def solve_with_reason_model(single_q_dict, user_answer_dict):

    # single_q_dict contains exactly ONE question
    q_num, q_data = list(single_q_dict.items())[0]
    question_text = q_data.get("question", "")
    options = q_data.get("options", {})
    user_option = user_answer_dict.get(q_num)

    prompt = f"""
You are helping a student understand one MCQ.

Question:
{question_text}

Options:
1. {options.get("1")}
2. {options.get("2")}
3. {options.get("3")}
4. {options.get("4")}

The student selected option: {user_option}

1. Determine internally which option is correct.
2. State whether the student is correct.
3. If incorrect, explain briefly why.
4. Keep explanation concise (2-4 lines).

Return ONLY JSON in this format:

{{
  "{q_num}": {{
    "correct_option": "X",
    "user_option": "{user_option}",
    "is_correct": true/false,
    "explanation": "Short explanation"
  }}
}}

Return raw JSON only.
Do not add commentary.
"""

    try:
        response = reason_model.generate_content(
            prompt,
            request_options={"timeout": 60}
        )

        if not response.candidates:
            return {}

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

def solve_in_batches(mcqs, user_answers, batch_size=3):
    all_results = {}
    items = list(mcqs.items())

    for i in range(0, len(items), batch_size):

        batch_raw = dict(items[i:i+batch_size])

        # Build smaller tutoring-style prompt batch
        batch = {}
        batch_user = {}

        for k, v in batch_raw.items():
            batch[k] = {
                "question": v.get("question", ""),
                "options": v.get("options", {})
            }
            batch_user[k] = user_answers[k]

        result = solve_with_reason_model(batch, batch_user)

        if not result:
            # Do not abort whole test
            for k in batch.keys():
                all_results[k] = {
                    "correct_option": None,
                    "user_option": user_answers[k],
                    "is_correct": None,
                    "explanation": "Evaluation failed for this question."
                }
            continue

        all_results.update(result)

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

        with st.spinner("Evaluating answers..."):
            correct_answers = solve_in_batches(first_fifty, user_answers, batch_size=3)

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




