# UGC NET Paper 1 – MCQ Solver (Gemini Powered)

## Deployment Instructions

### Run Locally

1. Clone or download the repository.
2. Create a `.env` file in the root directory.
3. Add your Google Gemini API key: GEMINI_API_KEY=your_api_key_here
4. Install dependencies: pip install -r requirements.txt
5. Run the application: streamlit run net_solver.py

### Deploy on Streamlit Cloud

1. Push the project to GitHub.
2. In Streamlit Cloud:
   - Go to **App → Manage App → Secrets**
   - Add: GEMINI_API_KEY = "your_api_key_here"
3. Deploy the app.

> Note: `.env` files are ignored on Streamlit Cloud. Use Secrets instead.

## Disclaimer

- Although titled for “Paper 1”, the application can process any MCQ-based PDF if the Gemini model is able to extract the content correctly.
- The application relies on Gemini’s parsing and reasoning capabilities. Numerical or data interpretation questions may occasionally produce incorrect evaluations.
- This tool was built primarily to assist in UGC NET preparation.

## Feedback

If you encounter issues or bugs, feel free to reach out:

**souhardyadas56@gmail.com**

## About the Author

Master’s student in Data Science with interests in:

- Data Analysis  
- Machine Learning  
- AI Applications  
- LLM-based Systems  

Open to internships and entry-level roles in data science, AI, or data analytics.
