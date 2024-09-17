import gradio as gr
import groq
import json
import time
import os
from threading import Thread
from queue import Queue
from dotenv import load_dotenv
from ratelimit import limits, sleep_and_retry

# Load environment variables from .env file
load_dotenv()

# Define rate limit: 29 calls per 60 seconds
CALLS = 29
RATE_LIMIT = 60

@sleep_and_retry
@limits(calls=CALLS, period=RATE_LIMIT)
def rate_limited_api_call(client, messages, max_tokens, is_final_answer=False):
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.2,
                response_format={"type": "json_object"}
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            if attempt == 2:
                if is_final_answer:
                    return {"title": "Error", "content": f"Failed to generate final answer after 3 attempts. Error: {str(e)}"}
                else:
                    return {"title": "Error", "content": f"Failed to generate step after 3 attempts. Error: {str(e)}", "next_action": "final_answer"}
            time.sleep(1)  # Wait for 1 second before retrying

def generate_response(client, prompt, queue):
    messages = [
        {"role": "system", "content": """
            You are an expert AI assistant that explains your reasoning step by step. 
            For each step, provide a title that describes what you're doing in that step, along with the content. 
            Decide if you need another step or if you're ready to give the final answer. 
            Respond in JSON format with 'title', 'content', and 'next_action' (either 'continue' or 'final_answer') keys. 

            Example of a valid JSON response:
                ```json
                {
                    "title": "Identifying Key Information",
                    "content": "To begin solving this problem, we need to carefully examine the given information and identify the crucial elements that will guide our solution process. This involves...",
                    "next_action": "continue"
                }```

            USE AS MANY REASONING STEPS AS POSSIBLE. AT LEAST 3. BE AWARE OF YOUR LIMITATIONS AS AN LLM AND WHAT YOU CAN AND CANNOT DO. 
            IN YOUR REASONING, INCLUDE EXPLORATION OF ALTERNATIVE ANSWERS. CONSIDER YOU MAY BE WRONG, AND IF YOU ARE WRONG IN YOUR REASONING, WHERE IT WOULD BE. 
            FULLY TEST ALL OTHER POSSIBILITIES. YOU CAN BE WRONG. WHEN YOU SAY YOU ARE RE-EXAMINING, ACTUALLY RE-EXAMINE, AND USE ANOTHER APPROACH TO DO SO. DO NOT JUST SAY YOU ARE RE-EXAMINING. 
            USE AT LEAST 3 METHODS TO DERIVE THE ANSWER. USE BEST PRACTICES. YOU ARE A WORLD-CLASS AI ASSISTANT.
            """},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": "Thank you! I will now think step by step following my instructions, starting at the beginning after decomposing the problem."}
    ]
    
    step_count = 1
    total_thinking_time = 0
    
    while True:
        start_time = time.time()
        step_data = rate_limited_api_call(client, messages, 300)
        end_time = time.time()
        thinking_time = end_time - start_time
        total_thinking_time += thinking_time
        
        step_title = f"Step {step_count}: {step_data.get('title', 'No Title')}"
        step_content = step_data.get('content', 'No Content')
        step_info = format_step(step_title, step_content, thinking_time)
        
        queue.put(step_info)
        
        messages.append({"role": "assistant", "content": json.dumps(step_data)})
        
        if step_data.get('next_action') == 'final_answer':
            break
        
        step_count += 1

    # Generate final answer
    messages.append({"role": "user", "content": "Please provide the final answer based on your reasoning above."})
    
    start_time = time.time()
    final_data = rate_limited_api_call(client, messages, 200, is_final_answer=True)
    end_time = time.time()
    thinking_time = end_time - start_time
    total_thinking_time += thinking_time
    
    final_answer = format_final_answer(final_data.get('content', 'No Content'), thinking_time, total_thinking_time)
    queue.put(final_answer)
    queue.put(None)  # Signal that we're done

def format_step(title, content, thinking_time):
    return f"""
    <details open>
        <summary><strong>{title}</strong></summary>
        <pre style="white-space: pre-wrap; word-wrap: break-word;">
{content}

Thinking time: {thinking_time:.2f} seconds
        </pre>
    </details>
    <br>
    """

def format_final_answer(content, thinking_time, total_time):
    return f"""
    <h3>Final Answer</h3>
    <pre style="white-space: pre-wrap; word-wrap: break-word;">
{content}

Thinking time for final answer: {thinking_time:.2f} seconds
Total thinking time: {total_time:.2f} seconds
    </pre>
    """

def on_submit(user_query):
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        yield "Please set the GROQ_API_KEY environment variable."
        return
    
    if not user_query:
        yield "Please enter a query to get started."
        return
    
    try:
        client = groq.Groq(api_key=api_key)
    except Exception as e:
        yield f"Failed to initialize Groq client. Error: {str(e)}"
        return
    
    queue = Queue()
    thread = Thread(target=generate_response, args=(client, user_query, queue))
    thread.start()
    
    output = ""
    while True:
        step = queue.get()
        if step is None:
            break
        output += step
        yield output

with gr.Blocks() as demo:
    gr.Markdown("# AI Reasoning Assistant")
    
    gr.Markdown("""
    This AI assistant breaks down complex problems into steps, providing detailed explanations for each part of its reasoning process.

    **How it works:**
    1. Enter your question in the text box below.
    2. The AI will think through the problem step-by-step.
    3. Each step of the reasoning process will appear in real-time.
    4. The final answer will be provided at the end.

    *Technical details: This prototype uses Llama-3.1 70b on Groq to create O1-like reasoning chains, aiming to improve output accuracy. It's powered by Groq for fast reasoning steps.*
    """)
    
    with gr.Row():
        with gr.Column():
            user_input = gr.Textbox(
                label="Enter your question:",
                placeholder="e.g., How many 'R's are in the word strawberry?",
                lines=3
            )
            submit_btn = gr.Button("Generate Response")
    
    with gr.Row():
        with gr.Column():
            output_html = gr.HTML()
    
    submit_btn.click(fn=on_submit, inputs=[user_input], outputs=output_html)

if __name__ == "__main__":
    demo.launch()