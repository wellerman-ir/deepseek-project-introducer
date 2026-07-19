# 🚀 DeepSeek Project Introducer

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/wellerman-ir/deepseek-project-introducer)](https://github.com/wellerman-ir/deepseek-project-introducer/stargazers)
[![GitHub issues](https://img.shields.io/github/issues/wellerman-ir/deepseek-project-introducer)](https://github.com/wellerman-ir/deepseek-project-introducer/issues)
[![GitHub forks](https://img.shields.io/github/forks/wellerman-ir/deepseek-project-introducer)](https://github.com/wellerman-ir/deepseek-project-introducer/network)

> Automatically introduce your entire project to DeepSeek AI for comprehensive analysis and insights

## ✨ Features

- 🚀 **Automatic File Discovery** - Scans and identifies all code files in your project
- 🎯 **Smart Filtering** - Excludes binary files, dependencies, and unnecessary directories
- 📝 **Structured Upload** - Sends files with proper formatting and syntax highlighting
- 🤖 **AI-Powered Analysis** - Leverages DeepSeek for comprehensive project understanding
- 📊 **Detailed Summary** - Generates project overview, architecture analysis, and improvement suggestions
- 💾 **Export Results** - Saves AI-generated summary as a Markdown file
- 📈 **Progress Tracking** - Real-time progress with statistics

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Google Chrome browser
- ChromeDriver (matching your Chrome version)
- downlaod Chrome driver from this address : 
    https://googlechromelabs.github.io/chrome-for-testing/#stable
- Then put the driver in root of this project .  
- [DeepSeek Chat](https://chat.deepseek.com) account

### Installation

```bash
# Clone the repository
git clone https://github.com/wellerman-ir/deepseek-project-introducer.git
cd deepseek-project-introducer

# Install dependencies
pip install -r requirements.txt
Usage
Start Chrome with remote debugging:

bash
chrome.exe --remote-debugging-port=9222 --user-data-dir="%TEMP%\selenium-profile"
Navigate to DeepSeek Chat (chat.deepseek.com) and sign in

Run the tool:

bash
python deepseek_introducer.py /path/to/your/project
📖 Documentation
Full documentation is available in the docs directory.

Basic Commands
bash
# Analyze your project
python deepseek_introducer.py /path/to/project

# With custom settings
python deepseek_introducer.py /path/to/project --port 9222 --wait 5 --max-size 10000

# Enable debug mode
python deepseek_introducer.py /path/to/project --debug
Options
Option	Description	Default
project_path	Path to your project directory	Required
--port, -p	Chrome debugging port	9222
--max-size, -m	Max file size in characters	5000
--wait, -w	Wait time between messages (seconds)	10
--debug	Enable debug logging	False
🎯 Example Output
text
======================================================================
PROJECT INTRODUCTION TO DEEPSEEK CHAT
======================================================================
Project: /home/user/my-awesome-project
Max File Size: 5000 chars
Wait Time: 10 seconds
======================================================================

Generating directory tree...
📁 my-awesome-project/
├── src/
│   ├── main.py (2.3 KB)
│   └── utils.py (1.8 KB)
└── tests/
    └── test_main.py (1.2 KB)

Found 3 code files to send
✓ Sent: File: src/main.py...
✅ All files sent! Generating summary...

======================================================================
PROJECT SUMMARY FROM DEEPSEEK
======================================================================
[AI-generated analysis...]
======================================================================
✅ Summary saved to: PROJECT_SUMMARY_DEEPSEEK.md
🛠️ Project Structure
text
deepseek-project-introducer/
├── deepseek_introducer.py   # Main script
├── requirements.txt          # Dependencies
├── README.md                # This file
├── LICENSE                  # MIT License
├── .gitignore              # Git ignore

🤝 Contributing
Contributions are welcome! Here's how you can help:

Fork the repository

Create a feature branch (git checkout -b feature/AmazingFeature)

Commit your changes (git commit -m 'Add some AmazingFeature')

Push to the branch (git push origin feature/AmazingFeature)

Open a Pull Request

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.

📝 License
Distributed under the MIT License. See LICENSE for more information.
