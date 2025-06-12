# ResumeLaTeXer

[![Fork me on GitHub](https://github.blog/wp-content/uploads/2008/12/forkme_right_green_007200.png?resize=149%2C149)](https://github.com/nareshbabunuli/ResumeLaTeXer)

[![GitHub](https://img.shields.io/badge/GitHub-ResumeLaTeXer-blue?style=for-the-badge&logo=github)](https://github.com/nareshbabunuli/ResumeLaTeXer)

An AI-powered Flask web application that converts PDF resumes into professional LaTeX format. ResumeLaTeXer uses Mistral AI to intelligently parse resume content and transform it into well-structured LaTeX documents.

## Features

- 📄 PDF to LaTeX Conversion: Extract and convert PDF resumes to LaTeX format
- 🤖 AI-Powered Parsing: Uses Mistral AI to intelligently structure resume content
- 🎨 Multiple Templates: Choose from different LaTeX templates for your resume
- 📱 Overleaf Integration: Easy export to Overleaf for PDF generation and editing
- 🔄 Smart Content Organization: Automatically structures sections like experience, education, and skills
- 🗑️ File Management: Delete individual files or all files at once with the Delete All button
- 🌐 Web Interface: User-friendly Flask web application for easy interaction

## How It Works

1. Upload your PDF resume through the web interface
2. The AI extracts and structures your content
3. Choose a LaTeX template
4. Get your professionally formatted LaTeX resume
5. Export to Overleaf for PDF generation

## Requirements

- Python 3.8+
- Flask
- Mistral AI API key
- PDF resume file

## Getting Your Mistral AI API Key

1. Go to [Mistral AI Platform](https://console.mistral.ai)
2. Sign up or log in to your account
3. Navigate to the API Keys section
4. Create a new API key
5. Copy the key and set it as an environment variable:
   ```bash
   # On Windows
   set MISTRAL_API_KEY=your_api_key_here

   # On Linux/Mac
   export MISTRAL_API_KEY=your_api_key_here
   ```

## Installation

```bash
pip install -r requirements.txt
```

## Usage

1. Set your Mistral AI API key in environment variables
2. Run the Flask application:
```bash
python app.py
```
3. Open your web browser and navigate to `http://localhost:5000`
4. Use the web interface to upload and process your resume

## File Management

The application provides two ways to manage your files:
- Individual file deletion: Click the trash icon next to any file to delete it
- Delete All: Use the "Delete All Files" button to remove all PDF and LaTeX files at once
  - A confirmation dialog will appear to prevent accidental deletions
  - This action cannot be undone

## Output

The tool generates a LaTeX file that you can:
- Upload to Overleaf for PDF generation
- Edit further in any LaTeX editor
- Use as a template for future resumes

## License

MIT License

## Project Structure

- `app.py`: The main Flask application script.
- `templates/`: Directory containing HTML templates and LaTeX resume templates.
- `output/`: Directory where generated resumes are saved.
- `upload/`: Directory for potential input files (e.g., data for resumes).