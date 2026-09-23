import streamlit as st
import json
import os
import pandas as pd
import datetime
import io
from docx import Document
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

st.set_page_config(page_title="AI Resume CI/CD Pipeline", layout="wide")

st.title("🚀 AI Resume CI/CD Pipeline")

# Constants for storage
STATE_FILE = "local_state.json"
APPS_FILE = "applications.csv"
DEFAULT_PROFILE = ""

def generate_docx(resume_md, strategy_md):
    doc = Document()
    doc.add_heading('Tailored Resume', 0)
    
    # Very basic markdown parser for docx
    for line in resume_md.split('\n'):
        if line.startswith('### '):
            doc.add_heading(line[4:].strip(), level=3)
        elif line.startswith('## '):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith('# '):
            doc.add_heading(line[2:].strip(), level=1)
        elif line.startswith('- '):
            doc.add_paragraph(line[2:], style='List Bullet')
        elif line.startswith('**') and line.endswith('**'):
             p = doc.add_paragraph()
             p.add_run(line[2:-2]).bold = True
        elif line.strip() != '':
            doc.add_paragraph(line)
            
    doc.add_page_break()
    doc.add_heading('Interview Strategy', 1)
    for line in strategy_md.split('\n'):
        if line.startswith('### '):
            doc.add_heading(line[4:].strip(), level=3)
        elif line.startswith('## '):
            doc.add_heading(line[3:].strip(), level=2)
        elif line.startswith('- '):
            doc.add_paragraph(line[2:], style='List Bullet')
        elif line.strip() != '':
            doc.add_paragraph(line)
            
    f = io.BytesIO()
    doc.save(f)
    f.seek(0)
    return f

# Helper functions for persistence
def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
                return state.get("master_profile", DEFAULT_PROFILE), state.get("chat_history", []), state.get("gemini_api_key", ""), state.get("current_salary", "")
        except Exception:
            return DEFAULT_PROFILE, [], "", ""
    return DEFAULT_PROFILE, [], "", ""

def save_state():
    with open(STATE_FILE, "w") as f:
        json.dump({
            "master_profile": st.session_state.master_profile,
            "chat_history": st.session_state.chat_history,
            "gemini_api_key": st.session_state.get("gemini_api_key", ""),
            "current_salary": st.session_state.get("current_salary", "")
        }, f)

# Initialization
if "initialized" not in st.session_state:
    prof, hist, saved_key, saved_salary = load_state()
    st.session_state.master_profile = prof
    st.session_state.chat_history = hist
    st.session_state.gemini_api_key = saved_key
    st.session_state.current_salary = saved_salary
    st.session_state.initialized = True

if "missing_requirements" not in st.session_state:
    st.session_state.missing_requirements = None

if "last_analysis_result" not in st.session_state:
    st.session_state.last_analysis_result = None

# Sidebar
st.sidebar.title("Agent Settings")
api_key = st.sidebar.text_input("Gemini API Key", type="password", value=st.session_state.get("gemini_api_key", ""))
current_salary = st.sidebar.text_input("Current Salary (e.g. $120k)", value=st.session_state.get("current_salary", ""))

if api_key != st.session_state.get("gemini_api_key", "") or current_salary != st.session_state.get("current_salary", ""):
    st.session_state.gemini_api_key = api_key
    st.session_state.current_salary = current_salary
    save_state()

# Using a valid API model string
MODEL_ID = "gemini-3.8-flash" 

if not api_key:
    st.sidebar.warning("Please enter your Gemini API Key to continue.")
    st.stop()

# Initialize Gemini Client
client = genai.Client(api_key=api_key)

# Sidebar: Extraction Agent
st.sidebar.header("💬 Extraction Agent")
st.sidebar.markdown("Chat with the AI to refine your Master Profile.")

# System instruction for extraction agent
EXTRACTION_SYSTEM_INSTRUCTION = """
You are an expert career coach AI. Your task is to interview the user to refine their Master Profile.
Ask the user questions to draw out more details. If the user provides new skills or experience, incorporate them into your understanding of their profile.
When you update the profile or receive new information, acknowledge the new skills or context concisely in 1-2 sentences. Do NOT output the entire updated profile or resume back to the user in the chat window.
Strict system constraint: Never hallucinate skills. Strictly exclude Bicep and GitHub Actions from all outputs.
"""

def extract_profile_from_chat():
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in st.session_state.chat_history])
    prompt = f"Based on the following chat history, generate the updated Master Profile. Keep all the original baseline skills unless explicitly removed by the user. Do not include introductory text, just the profile itself. Remember the strict constraint: Never hallucinate skills. Strictly exclude Bicep and GitHub Actions.\n\nBaseline Profile: {DEFAULT_PROFILE}\n\nChat History:\n{history_text}"
    
    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=EXTRACTION_SYSTEM_INSTRUCTION
            )
        )
        if response.text:
            st.session_state.master_profile = response.text.strip()
            save_state()
    except Exception as e:
        pass # Ignore extraction errors for now to keep chat flowing

# Display chat history
if len(st.session_state.chat_history) > 4:
    with st.sidebar.expander("Older Messages", expanded=False):
        for msg in st.session_state.chat_history[:-4]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
    for msg in st.session_state.chat_history[-4:]:
        with st.sidebar.chat_message(msg["role"]):
            st.markdown(msg["content"])
else:
    for msg in st.session_state.chat_history:
        with st.sidebar.chat_message(msg["role"]):
            st.markdown(msg["content"])

# Check if there are missing requirements to prompt about
if st.session_state.missing_requirements:
    system_prompt = f"The user tried to deploy their resume but is missing the following core requirements: {', '.join(st.session_state.missing_requirements)}. Ask them to clarify if they have these skills or how they want to address this gap."
    with st.sidebar.chat_message("assistant"):
        st.markdown(system_prompt)
    st.session_state.chat_history.append({"role": "assistant", "content": system_prompt})
    save_state()
    st.session_state.missing_requirements = None
    # We clear it so it doesn't prompt again, and the user can respond

chat_input = st.sidebar.chat_input("Tell me about your skills...")
if chat_input:
    # Add user message
    st.session_state.chat_history.append({"role": "user", "content": chat_input})
    save_state()
    with st.sidebar.chat_message("user"):
        st.markdown(chat_input)
    
    # Generate AI response
    try:
        history_contents = []
        for msg in st.session_state.chat_history[:-1]:
            role = "user" if msg["role"] == "user" else "model"
            history_contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=msg["content"])])
            )
        
        history_contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=chat_input)])
        )

        chat_response = client.models.generate_content(
            model=MODEL_ID,
            contents=history_contents,
            config=types.GenerateContentConfig(
                system_instruction=f"{EXTRACTION_SYSTEM_INSTRUCTION}\nCurrent Master Profile: {st.session_state.master_profile}"
            )
        )
        
        assistant_reply = chat_response.text
        with st.sidebar.chat_message("assistant"):
            st.markdown(assistant_reply)
        st.session_state.chat_history.append({"role": "assistant", "content": assistant_reply})
        save_state()
        
        # Update Master Profile in background
        extract_profile_from_chat()
        st.rerun()
        
    except Exception as e:
        st.sidebar.error(f"Chat error: {e}")

st.sidebar.subheader("Current Master Profile")
st.sidebar.code(st.session_state.master_profile, language="markdown")

# Main Panel with Tabs
tab1, tab2 = st.tabs(["Resume Pipeline", "Job Tracker"])

with tab1:
    st.header("Job Description Analysis")
    jd_text = st.text_area("Paste Target Job Description (JD) here", height=200)

    class AnalysisResult(BaseModel):
        aligned: bool = Field(description="True if the core requirements of the JD are met by the Master Profile, False otherwise.")
        missing_requirements: list[str] = Field(description="List of core requirements missing from the Master Profile, if any.")
        resume_markdown: str | None = Field(description="Tailored resume in Markdown format. None if aligned is False.")
        salary_negotiation_script: str | None = Field(description="Targeted salary negotiation script. None if aligned is False.")
        technical_questions: list[str] | None = Field(description="Three technical questions to ask a hiring manager. None if aligned is False.")

    if st.button("Deploy Resume"):
        if not jd_text.strip():
            st.warning("Please paste a Job Description first.")
        else:
            with st.spinner("Analyzing JD against Master Profile..."):
                pipeline_prompt = f"""
                Analyze the following Job Description (JD) against the user's Master Profile.
                
                Master Profile:
                {st.session_state.master_profile}
                
                User's Current Salary (for reference):
                {st.session_state.current_salary if st.session_state.current_salary else 'Not provided'}
                
                Job Description:
                {jd_text}
                
                Task:
                1. Map the JD requirements against the Master Profile.
                2. If a core requirement from the JD is missing in the Master Profile, set 'aligned' to False and list the missing core requirements in 'missing_requirements'.
                3. If aligned (core requirements are met or implicitly covered), set 'aligned' to True.
                4. If aligned, generate a tailored resume in markdown format in 'resume_markdown'.
                5. If aligned, generate a targeted salary negotiation script in 'salary_negotiation_script'. Use the user's Current Salary to suggest realistic expected ranges if possible.
                6. If aligned, generate three technical questions to ask a hiring manager in 'technical_questions'.
                
                Strict constraints:
                - Never hallucinate skills. Only use skills present in the Master Profile.
                - Strictly exclude Bicep and GitHub Actions from all outputs.
                """
                
                try:
                    response = client.models.generate_content(
                        model=MODEL_ID,
                        contents=pipeline_prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=AnalysisResult,
                        ),
                    )
                    
                    # Check response
                    result = response.text
                    if isinstance(result, str):
                        try:
                            result_data = json.loads(result)
                        except json.JSONDecodeError:
                            st.error("Failed to parse JSON response from LLM.")
                            st.stop()
                        
                        if not result_data.get("aligned", False):
                            missing = result_data.get("missing_requirements", [])
                            st.error("Core requirements missing! Halted generation.")
                            st.warning(f"Missing requirements: {', '.join(missing)}")
                            
                            # Set session state so chat prompts next refresh
                            st.session_state.missing_requirements = missing
                            st.session_state.last_analysis_result = None
                            st.rerun()
                        else:
                            st.session_state.last_analysis_result = result_data
                            
                except Exception as e:
                    st.error(f"Error during deployment: {e}")

    if st.session_state.last_analysis_result:
        result_data = st.session_state.last_analysis_result
        st.success("Profile is aligned! Resume Deployed.")
        
        resume_md = result_data.get("resume_markdown", "No resume generated.")
        script_md = result_data.get("salary_negotiation_script", "No script generated.")
        qs = result_data.get("technical_questions", [])
        
        strategy_md = f"### Salary Negotiation Script\n{script_md}\n\n### Technical Questions to Ask\n"
        for q in qs:
            strategy_md += f"- {q}\n"
        
        # Quick Log Form
        with st.expander("Log this Application to Job Tracker", expanded=True):
            with st.form("quick_log_form"):
                col1, col2 = st.columns(2)
                with col1:
                    log_company = st.text_input("Company Name")
                    log_title = st.text_input("Job Title")
                with col2:
                    log_website = st.text_input("Website (Optional)")
                
                log_submit = st.form_submit_button("Save Application")
                if log_submit and log_company and log_title:
                    new_app = pd.DataFrame([{
                        "Company": log_company,
                        "Title": log_title,
                        "Website": log_website,
                        "Date Applied": datetime.date.today().strftime("%Y-%m-%d"),
                        "Status": "Applied",
                        "Resume": resume_md,
                        "Strategy": strategy_md
                    }])
                    if os.path.exists(APPS_FILE):
                        df = pd.read_csv(APPS_FILE)
                        df = pd.concat([df, new_app], ignore_index=True)
                    else:
                        df = new_app
                    df.to_csv(APPS_FILE, index=False)
                    st.success(f"Logged application for {log_company}!")
        
        col1, col2 = st.columns([1, 1])
        with col1:
            st.subheader("📄 Tailored Resume")
        with col2:
            docx_file = generate_docx(resume_md, strategy_md)
            st.download_button(
                label="📥 Download as Word Doc",
                data=docx_file,
                file_name="resume.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            )
            
        st.code(resume_md, language="markdown")
        
        st.subheader("💡 Interview Strategy")
        st.markdown("### Salary Negotiation Script")
        st.markdown(script_md)
        
        st.markdown("### Technical Questions to Ask")
        for q in qs:
            st.markdown(f"- {q}")

with tab2:
    st.header("Job Tracker")
    
    # Display the CSV
    if os.path.exists(APPS_FILE):
        df = pd.read_csv(APPS_FILE)
        display_df = df.drop(columns=["Resume", "Strategy"], errors='ignore')
        st.dataframe(display_df, use_container_width=True)
        
        if "Resume" in df.columns:
            st.subheader("View Saved Resume")
            companies = df["Company"].tolist()
            if companies:
                selected_company = st.selectbox("Select an application to view details", companies)
                if selected_company:
                    app_row = df[df["Company"] == selected_company].iloc[0]
                    st.markdown(f"**Job Title:** {app_row['Title']}")
                    
                    with st.expander("View Resume"):
                        st.code(app_row.get("Resume", ""), language="markdown")
                        
                    with st.expander("View Interview Strategy"):
                        st.markdown(app_row.get("Strategy", ""))
    else:
        st.info("No applications logged yet.")
        
    st.subheader("Add Application Manually")
    with st.form("tracker_form"):
        col1, col2 = st.columns(2)
        with col1:
            t_company = st.text_input("Company")
            t_title = st.text_input("Job Title")
            t_website = st.text_input("Website (Optional)")
        with col2:
            t_date = st.date_input("Date Applied", datetime.date.today())
            t_status = st.selectbox("Status", ["Applied", "Interviewing", "Rejected", "Offer"])
            
        t_submit = st.form_submit_button("Add to Tracker")
        if t_submit and t_company and t_title:
            new_app = pd.DataFrame([{
                "Company": t_company,
                "Title": t_title,
                "Website": t_website,
                "Date Applied": t_date.strftime("%Y-%m-%d"),
                "Status": t_status,
                "Resume": "",
                "Strategy": ""
            }])
            if os.path.exists(APPS_FILE):
                df = pd.read_csv(APPS_FILE)
                df = pd.concat([df, new_app], ignore_index=True)
            else:
                df = new_app
            df.to_csv(APPS_FILE, index=False)
            st.success("Application added!")
            st.rerun()
