import os
import json
import PyPDF2
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
from dotenv import load_dotenv
import requests
import base64

# Load environment variables
load_dotenv()


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

    # List of models to try in order of preference
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

    # If all models failed, raise the last error
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

    # If all models failed, raise the last error
    if last_error:
        raise last_error
    else:
        raise Exception("All models failed without specific error")


def send_to_overleaf(latex_code: str, project_name: str = "Generated Resume") -> str:
    """
    Sends the LaTeX code to Overleaf and returns the project URL.
    Uses base64 encoding to handle large LaTeX content.
    """
    # Encode the LaTeX code in base64
    encoded_latex = base64.b64encode(latex_code.encode('utf-8')).decode('utf-8')

    # Create the Overleaf URL with the base64 encoded content
    overleaf_url = f"https://www.overleaf.com/docs?snip_uri=data:application/x-tex;base64,{encoded_latex}"

    print(f"[INFO] Generated Overleaf URL: {overleaf_url}")
    return overleaf_url


def save_latex_file(latex_code: str, output_tex: str = "resume.tex", send_to_overleaf_flag: bool = False):
    """
    Writes LaTeX code to output file and provides instructions for manual Overleaf upload.
    Returns the path to the saved LaTeX file.
    """
    # Ensure output directory exists
    output_dir = os.path.dirname(output_tex)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # Write the LaTeX code to the specified file
    with open(output_tex, 'w', encoding='utf-8') as f:
        f.write(latex_code)

    print(f"[INFO] LaTeX template saved to: {output_tex}")

    print("\n[INFO] To convert to PDF using Overleaf:")
    print("1. Go to https://www.overleaf.com")
    print("2. Create a new project")
    print("3. Upload the generated .tex file")
    print(f"4. The file is located at: {os.path.abspath(output_tex)}")

    return output_tex


def main():
    # ------------------
    # 1) Configuration
    # ------------------
    pdf_file = "upload/" + os.getenv("PDF_FILE_PATH")  # Path to your resume PDF

    # Get API key from environment variable for security
    api_key = os.getenv("MISTRAL_API_KEY")
    if not api_key:
        print("[ERROR] Please set MISTRAL_API_KEY environment variable")
        return

    chosen_template = "template1"  # or "template2"
    output_tex_filename = os.path.join('output', 'generated_resume.tex')
    send_to_overleaf_flag = True  # Set to True to automatically send to Overleaf

    try:
        # -----------------------------
        # 2) Extract text from the PDF
        # -----------------------------
        pdf_text = extract_text_from_pdf(pdf_file)
        print("[INFO] Extracted PDF text successfully.\n")

        # --------------------------------
        # 3) Convert PDF text -> JSON data
        # --------------------------------
        json_str = convert_resume_to_json(pdf_text, api_key)
        print("[INFO] JSON response from Mistral:\n", json_str, "\n")

        # Parse the JSON
        try:
            resume_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[ERROR] Failed to parse JSON. Error: {e}")
            return

        # ----------------------------------
        # 4) Load chosen LaTeX template file
        # ----------------------------------
        template_file = f"templates/{chosen_template}.tex"
        if not os.path.exists(template_file):
            print(f"[ERROR] Template file '{template_file}' does not exist.")
            return

        with open(template_file, "r", encoding="utf-8") as tf:
            template_str = tf.read()

        # ---------------------------------------
        # 5) Merge JSON + Template via Mistral
        # ---------------------------------------
        final_latex = convert_json_and_template_to_latex(resume_data, template_str, api_key)
        print("[INFO] Final LaTeX code from Mistral:\n")
        print(final_latex, "\n")

        # Create output directory if it doesn't exist
        if not os.path.exists('output'):
            os.makedirs('output')

        # ---------------------------------
        # 6) Save LaTeX file and optionally send to Overleaf
        # ---------------------------------
        saved_tex_file = save_latex_file(
            final_latex,
            output_tex=output_tex_filename,
            send_to_overleaf_flag=send_to_overleaf_flag
        )
        print(f"[INFO] LaTeX file saved successfully to: {saved_tex_file}")

    except Exception as e:
        print(f"[ERROR] Exception occurred: {e}")


if __name__ == "__main__":
    main()
