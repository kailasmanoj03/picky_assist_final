import streamlit as st
import openai
import os
import time
import json

# loading api key
openai.api_key = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY"))

st.set_page_config(page_title="Context-Locked AI Chatbot", page_icon="🤖")
st.title("🤖 Context-Locked AI Chatbot")

# session start
if 'training_content' not in st.session_state:
    st.session_state['training_content'] = ""
if 'emails' not in st.session_state:
    st.session_state['emails'] = []
if 'chat_history' not in st.session_state:
    st.session_state['chat_history'] = []
if 'assistant_id' not in st.session_state:
    st.session_state['assistant_id'] = None
if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = None
if 'file_id' not in st.session_state:
    st.session_state['file_id'] = None

# training using input text
st.subheader("Step 1: Provide Training Content")
context = st.text_area("Paste your FAQs, product details, etc. here:", height=200, value=st.session_state['training_content'])
if st.button("Save Context"):
    st.session_state['training_content'] = context
    # upload to openAI
    if context.strip():
        with st.spinner("Uploading context to OpenAI..."):
            file_obj = openai.files.create(
                file=context.encode("utf-8"),
                purpose="assistants"
            )
            st.session_state['file_id'] = file_obj.id
            st.success("Context saved and uploaded!")
            # assistant created
            instructions = (
                "You are a helpful assistant. Only answer questions using the uploaded training content. "
                "If a question is outside the provided content, reply: "
                "'I'm sorry, I can only answer questions based on the provided training content.'"
            )
            assistant = openai.beta.assistants.create(
                name="Context-Locked Assistant",
                instructions=instructions,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "send_email",
                            "description": "Send an email to the user.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "to": {"type": "string", "description": "Recipient email address"},
                                    "subject": {"type": "string", "description": "Email subject"},
                                    "body": {"type": "string", "description": "Email body"}
                                },
                                "required": ["to", "subject", "body"]
                            }
                        }
                    },
                    {
                        "type": "file_search"
                    }
                ],
                model="gpt-4o"
            )
            st.session_state['assistant_id'] = assistant.id
            st.session_state['thread_id'] = None  # Reset thread
    else:
        st.warning("Please enter some training content.")

# email input
st.subheader("Step 2: Enter Your Email")
email = st.text_input("Email Address")
if st.button("Save Email"):
    if email and "@" in email:
        st.session_state['emails'].append(email)
        st.success("Email saved!")
    else:
        st.warning("Please enter a valid email address.")

# Chat
st.subheader("Step 3: Chat with the AI (context-locked)")

def send_email(to: str, subject: str, body: str):
    print(f"Email to {to}: {subject}\n{body}")

def display_chat():
    for role, msg in st.session_state['chat_history']:
        if role == "user":
            st.markdown(f"**You:** {msg}")
        elif role == "assistant":
            st.markdown(f"**AI:** {msg}")

display_chat()

user_input = st.text_input("Ask a question:", key="user_input")
if st.button("Send") and user_input:
    st.session_state['chat_history'].append(("user", user_input))
    if not st.session_state.get('assistant_id'):
        st.warning("Please save your training context first.")
    else:
        # Creating thread if no thread
        if not st.session_state.get('thread_id'):
            thread = openai.beta.threads.create(
                # attaching files if needed
                # files=[file_obj.id]
            )
            st.session_state['thread_id'] = thread.id
        openai.beta.threads.messages.create(
            thread_id=st.session_state['thread_id'],
            role="user",
            content=user_input
        )
        # Run the assistant
        run = openai.beta.threads.runs.create(
            thread_id=st.session_state['thread_id'],
            assistant_id=st.session_state['assistant_id']
        )
       
        with st.spinner("Thinking"):
            while True:
                run_status = openai.beta.threads.runs.retrieve(
                    thread_id=st.session_state['thread_id'],
                    run_id=run.id
                )
                if run_status.status in ["completed", "failed"]:
                    break
                time.sleep(1)
        messages = openai.beta.threads.messages.list(
            thread_id=st.session_state['thread_id']
        )
        ai_msg = ""
        for m in reversed(messages.data):
            if m.role == "assistant":
                ai_msg = m.content[0].text.value
                break
        if hasattr(run_status, "required_action") and run_status.required_action:
            actions = run_status.required_action.submit_tool_outputs.tool_calls
            for action in actions:
                if action.function.name == "send_email":
                    args = json.loads(action.function.arguments)
                    send_email(args['to'], args['subject'], args['body'])
                    ai_msg += "\n\n(Email sent simulation.)"
        st.session_state['chat_history'].append(("assistant", ai_msg))
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

st.divider()
st.info("Deploy this app on Streamlit Cloud and store your OpenAI API key in Secrets as")