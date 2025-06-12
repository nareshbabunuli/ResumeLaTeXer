import os
import json
import PyPDF2
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
import requests
import base64
from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename
import tempfile
import uuid
import threading
import time

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Required for flash messages

# Use /tmp for file storage in Vercel environment
TEMP_DIR = tempfile.gettempdir()
app.config['UPLOAD_FOLDER'] = os.path.join(TEMP_DIR, 'upload_resumes')
app.config['OUTPUT_FOLDER'] = os.path.join(TEMP_DIR, 'output_latex')

app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload and output directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def delete_old_files():
    # This scheduled cleanup might not be effective in a serverless environment
    # as instances are ephemeral. Consider other cleanup strategies if needed.
    print("[INFO] Running scheduled file cleanup...")
    for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER']]:
        # Ensure the directory exists before listing to avoid errors
        if not os.path.exists(folder):
            os.makedirs(folder, exist_ok=True)
            continue # Skip if just created, no files to delete yet

        for filename in os.listdir(folder):
            filepath = os.path.join(folder, filename)
            if os.path.isfile(filepath):
                # Delete files older than 24 hours
                if (time.time() - os.path.getmtime(filepath)) > 24 * 3600:
                    try:
                        os.remove(filepath)
                        print(f"[INFO] Deleted old file: {filepath}")
                    except Exception as e:
                        print(f"[ERROR] Error deleting file {filepath}: {e}")

# The cleanup thread will run only as long as the serverless instance is active,
# which might be very short. Manual deletion or re-uploading will handle most cases.
cleanup_thread = threading.Thread(target=delete_old_files)
cleanup_thread.daemon = True # Allows the main program to exit even if this thread is running
cleanup_thread.start()

def extract_text_from_pdf(filepath: str) -> str:
    """
    Extract text from each page of a PDF using PyPDF2 and return as a single string.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"PDF file not found: {filepath}")

    extracted_pages = []
    try:
        with open(filepath, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            for page_num in range(len(reader.pages)):
                page_text = reader.pages[page_num].extract_text()
                extracted_pages.append(page_text)
        return "\n".join(extracted_pages)
    except Exception as e:
        raise Exception(f"Error extracting text from PDF: {str(e)}")

def convert_resume_to_json(pdf_text: str, api_key: str) -> str:
    """
    Sends extracted PDF text to Mistral, requesting structured JSON.
    Tries different models if rate limit is hit.
    """
    client = MistralClient(api_key=api_key)

    models = [
        "mistral-large-latest",
        "mistral-medium-latest",
        "mistral-small-latest",
    ]

    messages = [
        ChatMessage(
            role="system",
            content=(
                "You are a helpful assistant that converts resume text into structured JSON. "
                "Return ONLY the JSON object—no code blocks, no extra commentary."
            )
        ),
        ChatMessage(
            role="user",
            content=f"""
Convert the following resume text into a JSON object with these keys (if present):
- name
- contact_information
- professional_summary
- key_skills
- work_experience
- education
- projects
- achievements

For contact_information, parse out:
- address
- email
- phone
- linkedin
- github
- portfolio

Keep the original text. Do NOT rewrite or summarize it.
Use arrays for bullet points.

Resume text:
{pdf_text}

Return ONLY the JSON object, with no code fences or explanations.
"""
        )
    ]

    last_error = None
    for model in models:
        try:
            print(f"[INFO] Trying model: {model}")
            response = client.chat(
                model=model,
                messages=messages,
                temperature=0.0
            )

            generated_text = response.choices[0].message.content.strip()

            if generated_text.startswith("```"):
                first_delim = generated_text.find("\n") + 1
                last_delim = generated_text.rfind("```")
                generated_text = generated_text[first_delim:last_delim].strip()

            return generated_text

        except Exception as e:
            last_error = e
            print(f"[WARNING] Failed with model {model}: {str(e)}")
            continue

    if last_error:
        raise last_error
    else:
        raise Exception("All models failed without specific error")

def convert_json_and_template_to_latex(json_data: dict, template_str: str, api_key: str) -> str:
    """
    Converts JSON data and LaTeX template to final LaTeX code using Mistral.
    """
    client = MistralClient(api_key=api_key)

    models = [
        "mistral-large-latest",
        "mistral-medium-latest",
        "mistral-small-latest",
    ]

    json_string = json.dumps(json_data, indent=2)
    messages = [
        ChatMessage(
            role="system",
            content=(
                "You are a helpful assistant that merges JSON resume data into a provided LaTeX template. "
                "Return ONLY valid LaTeX—no code fences, no extra commentary."
            )
        ),
        ChatMessage(
            role="user",
            content=f"""
Below is a LaTeX resume template, followed by JSON data.
Inject the JSON values into the correct places in the template. 
If a JSON field doesn't apply, skip it gracefully.

--- TEMPLATE START ---
{template_str}
--- TEMPLATE END ---

--- JSON DATA START ---
{json_string}
--- JSON DATA END ---

Requirements:
1. Return valid LaTeX only (no triple backticks).
2. Preserve the template structure but fill with JSON data.
3. Omit any missing fields from the JSON gracefully.
"""
        )
    ]

    last_error = None
    for model in models:
        try:
            print(f"[INFO] Trying model: {model}")
            response = client.chat(
                model=model,
                messages=messages,
                temperature=0.0
            )

            latex_code = response.choices[0].message.content.strip()

            if latex_code.startswith("```"):
                first_delim = latex_code.find("\n") + 1
                last_delim = latex_code.rfind("```")
                latex_code = latex_code[first_delim:last_delim].strip()

            return latex_code

        except Exception as e:
            last_error = e
            print(f"[WARNING] Failed with model {model}: {str(e)}")
            continue

    if last_error:
        raise last_error
    else:
        raise Exception("All models failed without specific error")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    
    file = request.files['file']
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        try:
            # Extract text from PDF
            pdf_text = extract_text_from_pdf(filepath)
            
            # Convert to JSON using Mistral
            api_key = request.form.get('api_key') # Get API key from form data
            if not api_key:
                flash('Mistral API key not provided.')
                return redirect(url_for('index'))
            
            json_data = convert_resume_to_json(pdf_text, api_key)
            return jsonify({'success': True, 'data': json.loads(json_data)})
            
        except Exception as e:
            flash(f'Error processing file: {str(e)}')
            return redirect(url_for('index'))
    
    flash('Invalid file type. Please upload a PDF file.')
    return redirect(url_for('index'))

@app.route('/generate', methods=['POST'])
def generate_resume():
    try:
        data = request.json
        template_name = data.get('template', 'template1')
        resume_data = data.get('resume_data')
        api_key = data.get('api_key') # Get API key from JSON data

        if not api_key:
            return jsonify({'success': False, 'error': 'Mistral API key not provided.'})

        # Load template
        # If template is a path (for custom template), read its content
        if template_name.startswith('template'):
            # This is a pre-defined template
            template_path = os.path.join('templates', f'{template_name}.tex')
            if not os.path.exists(template_path):
                return jsonify({'success': False, 'error': f'Template file {template_name}.tex not found.'}), 404
            with open(template_path, 'r', encoding='utf-8') as f:
                template_str = f.read()
        else:
            # This is a custom template content provided directly
            template_str = template_name # template_name now holds the actual template content

        # Generate LaTeX
        latex_code = convert_json_and_template_to_latex(resume_data, template_str, api_key)

        # Save to permanent file in output folder
        output_filename = f"resume_{uuid.uuid4().hex}.tex"
        output_filepath = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
        with open(output_filepath, 'w', encoding='utf-8') as f:
            f.write(latex_code)

        # Construct URL for the permanent file
        permanent_file_url = url_for('get_file_content', file_type='latex', filename=output_filename, _external=True)

        return jsonify({'success': True, 'file_url': permanent_file_url})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/temp_files/<filename>')
def serve_temp_file(filename):
    # Ensure the file is actually in the temporary directory created by tempfile
    # For simplicity, we'll assume tempfile creates in the system temp directory
    # In a real app, you might want a dedicated temporary upload folder.
    try:
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, filename)
        return send_file(filepath, mimetype='application/x-tex')
    except Exception as e:
        return str(e), 404

@app.route('/list_files')
def list_files():
    uploaded_pdfs = []
    generated_latex = []

    for filename in os.listdir(app.config['UPLOAD_FOLDER']):
        if allowed_file(filename):
            uploaded_pdfs.append(filename)
    
    for filename in os.listdir(app.config['OUTPUT_FOLDER']):
        if filename.endswith('.tex'):
            generated_latex.append(filename)
    
    return jsonify({
        'uploaded_pdfs': uploaded_pdfs,
        'generated_latex': generated_latex
    })

@app.route('/delete_file', methods=['POST'])
def delete_file():
    data = request.json
    filename = data.get('filename')
    file_type = data.get('file_type') # 'pdf' or 'latex'

    if not filename or not file_type:
        return jsonify({'success': False, 'error': 'Filename and file type are required.'}), 400

    if file_type == 'pdf':
        folder = app.config['UPLOAD_FOLDER']
    elif file_type == 'latex':
        folder = app.config['OUTPUT_FOLDER']
    else:
        return jsonify({'success': False, 'error': 'Invalid file type.'}), 400

    filepath = os.path.join(folder, filename)

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            return jsonify({'success': True, 'message': f'{filename} deleted.'})
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error deleting file: {str(e)}'}), 500
    else:
        return jsonify({'success': False, 'error': f'{filename} not found.'}), 404

@app.route('/delete_all_files', methods=['POST'])
def delete_all_files():
    try:
        # Delete all files in upload folder
        for filename in os.listdir(app.config['UPLOAD_FOLDER']):
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            if os.path.isfile(filepath):
                os.remove(filepath)

        # Delete all files in output folder
        for filename in os.listdir(app.config['OUTPUT_FOLDER']):
            filepath = os.path.join(app.config['OUTPUT_FOLDER'], filename)
            if os.path.isfile(filepath):
                os.remove(filepath)

        return jsonify({'success': True, 'message': 'All files deleted successfully.'})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error deleting files: {str(e)}'}), 500

@app.route('/get_file_content')
def get_file_content():
    filename = request.args.get('filename')
    file_type = request.args.get('file_type') # 'pdf' or 'latex'

    if not filename or not file_type:
        return jsonify({'success': False, 'error': 'Filename and file type are required.'}), 400

    if file_type == 'pdf':
        folder = app.config['UPLOAD_FOLDER']
    elif file_type == 'latex':
        folder = app.config['OUTPUT_FOLDER']
    else:
        return jsonify({'success': False, 'error': 'Invalid file type.'}), 400

    filepath = os.path.join(folder, filename)

    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({'success': True, 'content': content})
        except Exception as e:
            return jsonify({'success': False, 'error': f'Error reading file: {str(e)}'}), 500
    else:
        return jsonify({'success': False, 'error': f'{filename} not found.'}), 404

@app.route('/process_existing_pdf', methods=['POST'])
def process_existing_pdf():
    data = request.json
    filename = data.get('filename')
    api_key = data.get('api_key')

    if not filename or not api_key:
        return jsonify({'success': False, 'error': 'Filename and API key are required.'}), 400

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

    if not os.path.exists(filepath):
        return jsonify({'success': False, 'error': 'PDF file not found.'}), 404

    try:
        pdf_text = extract_text_from_pdf(filepath)
        json_data = convert_resume_to_json(pdf_text, api_key)
        return jsonify({'success': True, 'data': json.loads(json_data)})
    except Exception as e:
        return jsonify({'success': False, 'error': f'Error processing existing PDF: {str(e)}'}), 500

@app.route('/github_stats')
def github_stats():
    repo_owner = "nareshbabunuli"
    repo_name = "ResumeLaTeXer"
    api_url = f"https://api.github.com/repos/{repo_owner}/{repo_name}"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status()  # Raise an exception for HTTP errors
        repo_data = response.json()
        stars = repo_data.get('stargazers_count', 0)
        return jsonify({'stars': stars})
    except requests.exceptions.RequestException as e:
        print(f"Error fetching GitHub stars: {e}")
        return jsonify({'error': 'Could not fetch GitHub stars'}), 500

if __name__ == '__main__':
    app.run(debug=True)
