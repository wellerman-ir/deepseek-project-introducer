#!/usr/bin/env python
"""
Project Introducer - Automatically introduce a project to DeepSeek Chat

This tool connects to a Chrome browser with remote debugging enabled,
then systematically sends project files to DeepSeek Chat for analysis.
"""

import os
import sys
import time
import argparse
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Set
import json
from datetime import datetime
import re
import logging
from dataclasses import dataclass
from enum import Enum

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException, TimeoutException

# Version
__version__ = "1.0.0"


class LogLevel(Enum):
    """Logging levels for the application"""
    DEBUG = logging.DEBUG
    INFO = logging.INFO
    WARNING = logging.WARNING
    ERROR = logging.ERROR


@dataclass
class FileInfo:
    """Information about a project file"""
    path: Path
    relative_path: str
    size: int
    extension: str
    is_code: bool


class ProjectIntroducer:
    """
    Main class for introducing a project to DeepSeek Chat.
    
    This class handles:
    - Connecting to Chrome via remote debugging
    - Scanning project directories
    - Sending files to DeepSeek Chat
    - Managing the conversation flow
    """
    
    # Default configuration
    DEFAULT_CONFIG = {
        'debug_port': 9222,
        'max_file_size': 5000,
        'wait_time': 10,
        'max_retries': 3,
        'chunk_size': 500,
        'timeout_initial': 20,
        'timeout_response': 60,
        'summary_wait': 30,
    }
    
    # DeepSeek Chat specific selectors
    CHAT_SELECTORS = {
        'input': [
            'textarea[placeholder*="Message"]',
            'textarea[placeholder*="Ask"]',
            'textarea[placeholder*="输入"]',
            'textarea[placeholder*="发送"]',
            'div[contenteditable="true"][role="textbox"]',
            '.chat-input textarea',
            '.input-area textarea',
            '#chat-input',
            '[data-testid="chat-input"]',
            'textarea'
        ],
        'send_button': [
            'button[type="submit"]',
            'button[aria-label*="Send"]',
            'button[aria-label*="发送"]',
            'button[aria-label*="Submit"]',
            '.send-button',
            '[data-testid="send-button"]',
            'button:has(svg)',
            '.chat-send-btn'
        ],
        'response': [
            '.message-response',
            '.assistant-message',
            '.ai-message',
            '[data-role="assistant"]',
            '.chat-message:last-child',
            '.message:last-child',
            '.assistant-content',
            '.deepseek-chat-message',
            '[class*="message"]:last-child'
        ],
        'loading': [
            '.loading',
            '.typing',
            '.thinking',
            '.generating',
            '[data-state="loading"]',
            '.animate-pulse',
            '.loader'
        ]
    }
    
    # Default excluded directories
    DEFAULT_EXCLUDED_DIRS = {
        '__pycache__', 'node_modules', '.git', 'venv', 
        'env', 'dist', 'build', '.idea', '.vscode',
        'coverage', '.pytest_cache', '.next', '.nuxt',
        'target', 'out', 'bin', 'obj', 'tmp', 'temp',
        'logs', 'uploads', 'downloads', 'cache',
        '.venv', 'venv', 'env', '.env'
    }
    
    # Default excluded extensions
    DEFAULT_EXCLUDED_EXTENSIONS = {
        '.pyc', '.pyo', '.pyd', '.so', '.dll', '.dylib',
        '.exe', '.msi', '.bin', '.class', '.jar',
        '.mp4', '.mp3', '.wav', '.jpg', '.jpeg', '.png', 
        '.gif', '.bmp', '.ico', '.svg', '.webp',
        '.zip', '.tar', '.gz', '.rar', '.7z', '.bz2',
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', 
        '.ppt', '.pptx', '.odt',
        '.pyc', '.pyo', '.pyd'
    }
    
    # Code file extensions
    CODE_EXTENSIONS = {
        '.py', '.js', '.ts', '.jsx', '.tsx', '.html', '.css', 
        '.scss', '.sass', '.less', '.json', '.xml', '.yaml', 
        '.yml', '.toml', '.md', '.rst', '.txt', '.sh', '.bash', 
        '.zsh', '.bat', '.cmd', '.ps1',
        '.cpp', '.c', '.h', '.hpp', '.java', '.kt', '.kts', 
        '.go', '.rs', '.rb', '.php', '.lua', '.r', '.swift', 
        '.dart', '.sql', '.awk', '.sed', '.vim', '.lua',
        '.vue', '.svelte', '.scala', '.clj', '.cljs',
        '.tf', '.hcl', '.proto', '.graphql', '.gql',
        '.sqlite', '.db', '.sql', '.csv'
    }
    
    def __init__(
        self, 
        project_path: str, 
        debug_port: int = 9222, 
        max_file_size: int = 5000,
        config: Optional[Dict] = None
    ):
        """
        Initialize the ProjectIntroducer for DeepSeek Chat.
        
        Args:
            project_path: Path to the project directory
            debug_port: Chrome remote debugging port
            max_file_size: Maximum file size to send (in characters)
            config: Additional configuration options
        """
        self.project_path = Path(project_path).resolve()
        self.debug_port = debug_port
        self.max_size = max_file_size
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        
        # State variables
        self.driver = None
        self.wait = None
        self.processed_files: List[str] = []
        self.finish_signal = "__FILES_COMPLETE__"
        self.is_deepseek = True  # Flag for DeepSeek-specific handling
        
        # Load configuration
        self.excluded_dirs = self.DEFAULT_EXCLUDED_DIRS.copy()
        self.excluded_extensions = self.DEFAULT_EXCLUDED_EXTENSIONS.copy()
        self.code_extensions = self.CODE_EXTENSIONS.copy()
        self.chat_selectors = self.CHAT_SELECTORS.copy()
        
        # Setup logging
        self.setup_logging()
        
        # Statistics
        self.stats = {
            'total_files': 0,
            'sent_files': 0,
            'failed_files': 0,
            'total_size': 0,
            'start_time': None,
            'end_time': None
        }
        
        self.logger.info(f"ProjectIntroducer initialized for DeepSeek Chat")
        self.logger.info(f"Project: {self.project_path}")
    
    def setup_logging(self, level: LogLevel = LogLevel.INFO):
        """Setup logging configuration"""
        self.logger = logging.getLogger('ProjectIntroducer')
        self.logger.setLevel(level.value)
        
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(level.value)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%H:%M:%S'
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
    
    def filter_bad_chars(self, text: str) -> str:
        """
        Remove characters that ChromeDriver doesn't support.
        
        Args:
            text: Input text to filter
            
        Returns:
            Filtered text containing only supported characters
        """
        # Remove non-BMP characters (emojis, special symbols)
        filtered = ''.join(c for c in text if ord(c) <= 0xFFFF)
        
        # Remove control characters except common ones
        filtered = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', filtered)
        
        return filtered
    
    def connect_to_chrome(self) -> bool:
        """
        Connect to Chrome with remote debugging.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            options = Options()
            options.add_experimental_option("debuggerAddress", f"127.0.0.1:{self.debug_port}")
            self.driver = webdriver.Chrome(options=options)
            self.wait = WebDriverWait(self.driver, self.config['timeout_initial'])
            
            time.sleep(3)
            
            self.logger.info(f"Connected to Chrome on port {self.debug_port}")
            self.logger.info(f"Current URL: {self.driver.current_url}")
            
            # Get page title for confirmation
            try:
                title = self.driver.title
                self.logger.info(f"Page title: {title}")
                if 'deepseek' in title.lower():
                    self.logger.info("✓ DeepSeek Chat detected!")
                else:
                    self.logger.warning("⚠️  This doesn't appear to be DeepSeek Chat")
                    self.logger.warning("Make sure you're on the DeepSeek Chat page")
            except:
                pass
            
            # Check if we're on DeepSeek
            current_url = self.driver.current_url
            if 'deepseek' not in current_url.lower():
                self.logger.warning(f"Current URL doesn't contain 'deepseek': {current_url}")
                self.logger.warning("Please navigate to DeepSeek Chat in Chrome")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to connect to Chrome: {e}")
            self.logger.info("\nTo fix this, run Chrome with remote debugging:")
            self.logger.info(f'chrome.exe --remote-debugging-port={self.debug_port} --user-data-dir="%TEMP%\\selenium-profile"')
            return False
    
    def find_input_box(self, retry_count: int = 3) -> Optional[webdriver.remote.webelement.WebElement]:
        """
        Find the DeepSeek chat input box with retry logic.
        
        Args:
            retry_count: Number of retry attempts
            
        Returns:
            WebElement or None if not found
        """
        for attempt in range(retry_count):
            try:
                # Try all configured selectors
                for selector in self.chat_selectors['input']:
                    try:
                        element = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        if element and element.is_displayed():
                            self.logger.debug(f"Found input using selector: {selector}")
                            return element
                    except:
                        continue
                
                # For DeepSeek specifically: try to find by placeholder text
                try:
                    elements = self.driver.find_elements(By.TAG_NAME, "textarea")
                    for el in elements:
                        if el.is_displayed():
                            placeholder = el.get_attribute("placeholder")
                            if placeholder and any(keyword in placeholder.lower() for keyword in ['message', 'ask', 'type', '输入']):
                                return el
                except:
                    pass
                
                # Try to find contenteditable div (common in DeepSeek)
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, '[contenteditable="true"]')
                    for el in elements:
                        if el.is_displayed() and el.get_attribute("role") == "textbox":
                            return el
                except:
                    pass
                
                time.sleep(1)
                
            except StaleElementReferenceException:
                self.logger.warning(f"Stale element, retry {attempt + 1}/{retry_count}")
                time.sleep(1)
            except Exception as e:
                self.logger.warning(f"Error finding input: {e}")
                time.sleep(1)
        
        return None
    
    def find_send_button(self) -> Optional[webdriver.remote.webelement.WebElement]:
        """
        Find the send button in DeepSeek Chat.
        
        Returns:
            WebElement or None if not found
        """
        # Try configured selectors
        for selector in self.chat_selectors['send_button']:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for element in elements:
                    if element.is_displayed() and element.is_enabled():
                        # Check if it's likely a send button
                        aria_label = element.get_attribute("aria-label") or ""
                        text = element.text.lower()
                        if any(keyword in (aria_label + text) for keyword in ['send', 'submit', '发送', 'arrow', '→']):
                            self.logger.debug(f"Found send button using selector: {selector}")
                            return element
            except:
                continue
        
        # For DeepSeek: Look for SVG send icon
        try:
            # Find all SVG elements that might be send icons
            svgs = self.driver.find_elements(By.TAG_NAME, "svg")
            for svg in svgs:
                try:
                    parent = svg.find_element(By.XPATH, "./..")
                    if parent.is_displayed() and parent.is_enabled():
                        # Check if it's a button or clickable
                        if parent.tag_name == "button" or parent.get_attribute("role") == "button":
                            return parent
                except:
                    continue
        except:
            pass
        
        # Fallback: find any button with send-related text
        try:
            buttons = self.driver.find_elements(By.TAG_NAME, "button")
            for btn in buttons:
                if btn.is_displayed() and btn.is_enabled():
                    text = btn.text.lower()
                    aria = (btn.get_attribute("aria-label") or "").lower()
                    combined = text + " " + aria
                    if any(word in combined for word in ['send', 'submit', 'post', '发送', 'arrow']):
                        return btn
        except:
            pass
        
        return None
    
    def wait_for_loading_complete(self, timeout: int = 30):
        """
        Wait for DeepSeek to finish generating response.
        
        Args:
            timeout: Maximum time to wait in seconds
        """
        try:
            # Check for loading indicators
            start_time = time.time()
            while time.time() - start_time < timeout:
                loading_found = False
                
                # Check various loading indicators
                for selector in self.chat_selectors['loading']:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        for el in elements:
                            if el.is_displayed():
                                loading_found = True
                                break
                        if loading_found:
                            break
                    except:
                        continue
                
                if not loading_found:
                    # Also check for "thinking" text
                    try:
                        page_text = self.driver.find_element(By.TAG_NAME, "body").text
                        if "thinking" in page_text.lower() or "generating" in page_text.lower():
                            loading_found = True
                    except:
                        pass
                
                if not loading_found:
                    # Check if response is complete by looking for assistant message
                    try:
                        messages = self.driver.find_elements(By.CSS_SELECTOR, '.assistant-message, .message-response, [data-role="assistant"]')
                        if messages and messages[-1].is_displayed():
                            # Check if it's still loading
                            if "..." in messages[-1].text[-10:]:
                                loading_found = True
                            else:
                                return
                    except:
                        pass
                
                if loading_found:
                    time.sleep(1)
                else:
                    break
                    
        except Exception as e:
            self.logger.debug(f"Error waiting for loading: {e}")
    
    def send_message(self, message: str) -> bool:
        """
        Send a message to DeepSeek Chat.
        
        Args:
            message: Message to send
            
        Returns:
            bool: True if sent successfully
        """
        # Filter out bad characters
        filtered_message = self.filter_bad_chars(message)
        
        if len(filtered_message) < len(message) * 0.5:
            self.logger.warning(
                f"Many characters filtered out. "
                f"Original: {len(message)}, Filtered: {len(filtered_message)}"
            )
        
        for attempt in range(self.config['max_retries']):
            try:
                # Find input box
                input_box = self.find_input_box()
                if not input_box:
                    self.logger.error(f"Could not find input box (attempt {attempt + 1})")
                    if attempt < self.config['max_retries'] - 1:
                        time.sleep(2)
                        continue
                    return False
                
                # Click to focus
                self.driver.execute_script("arguments[0].focus();", input_box)
                time.sleep(0.5)
                
                # Clear the input using JavaScript (more reliable)
                self.driver.execute_script("arguments[0].value = '';", input_box)
                time.sleep(0.2)
                
                # Try to click to ensure focus
                input_box.click()
                time.sleep(0.3)
                
                # Truncate if too long
                if len(filtered_message) > 10000:
                    self.logger.warning(
                        f"Message too long ({len(filtered_message)} chars), truncating..."
                    )
                    filtered_message = filtered_message[:10000] + "\n\n[Message truncated]"
                
                # Send message
                if input_box.tag_name == "textarea" or input_box.tag_name == "input":
                    # Send in chunks to avoid issues
                    chunk_size = self.config['chunk_size']
                    for i in range(0, len(filtered_message), chunk_size):
                        chunk = filtered_message[i:i+chunk_size]
                        input_box.send_keys(chunk)
                        time.sleep(0.02)
                else:
                    # Contenteditable div
                    self.driver.execute_script(
                        f"arguments[0].textContent = arguments[1];",
                        input_box,
                        filtered_message
                    )
                    # Trigger input event
                    self.driver.execute_script(
                        "arguments[0].dispatchEvent(new Event('input', {bubbles: true}));",
                        input_box
                    )
                
                time.sleep(0.5)
                
                # Find and click send button
                send_button = self.find_send_button()
                if send_button:
                    self.driver.execute_script("arguments[0].click();", send_button)
                else:
                    # Try Enter key (works for DeepSeek)
                    if input_box.tag_name == "textarea" or input_box.tag_name == "input":
                        input_box.send_keys(Keys.ENTER)
                    else:
                        # For contenteditable, use JavaScript to simulate Enter
                        self.driver.execute_script(
                            """
                            var event = new KeyboardEvent('keydown', {
                                key: 'Enter',
                                keyCode: 13,
                                which: 13,
                                bubbles: true
                            });
                            arguments[0].dispatchEvent(event);
                            """,
                            input_box
                        )
                
                # Log success (truncated)
                preview = filtered_message[:80].replace('\n', ' ')
                if len(filtered_message) > 80:
                    preview += '...'
                self.logger.info(f"Sent: {preview}")
                
                # Wait for DeepSeek to start processing
                time.sleep(2)
                
                # Wait for loading to complete
                self.wait_for_loading_complete(timeout=self.config['timeout_response'])
                
                return True
                
            except StaleElementReferenceException:
                self.logger.warning(f"Stale element, retry {attempt + 1}/{self.config['max_retries']}")
                time.sleep(2)
            except Exception as e:
                self.logger.warning(f"Send error (attempt {attempt + 1}): {e}")
                time.sleep(2)
        
        return False
    
    def get_directory_tree(self) -> str:
        """
        Generate a directory tree of the project.
        
        Returns:
            String representation of the directory tree
        """
        def build_tree(path: Path, prefix: str = "", is_last: bool = True) -> List[str]:
            lines = []
            
            # Get items
            items = []
            try:
                for item in sorted(path.iterdir()):
                    if item.name.startswith('.'):
                        continue
                    if item.name in self.excluded_dirs:
                        continue
                    if item.is_file() and item.suffix.lower() in self.excluded_extensions:
                        continue
                    items.append(item)
            except PermissionError:
                return [f"{prefix}└── [Permission Denied]"]
            
            # Sort: directories first, then files
            items.sort(key=lambda x: (not x.is_dir(), x.name.lower()))
            
            for i, item in enumerate(items):
                is_last_item = (i == len(items) - 1)
                connector = "└── " if is_last_item else "├── "
                
                if item.is_dir():
                    lines.append(f"{prefix}{connector}{item.name}/")
                    extension = "    " if is_last_item else "│   "
                    lines.extend(build_tree(item, prefix + extension, is_last_item))
                else:
                    try:
                        size = item.stat().st_size
                        size_str = self._format_size(size)
                    except:
                        size_str = "? B"
                    lines.append(f"{prefix}{connector}{item.name} ({size_str})")
            
            return lines
        
        tree_lines = [f"📁 {self.project_path.name}/"]
        tree_lines.extend(build_tree(self.project_path))
        return "\n".join(tree_lines)
    
    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def get_code_files(self) -> List[Tuple[Path, str]]:
        """
        Get all code files with their relative paths.
        
        Returns:
            List of (Path, relative_path) tuples
        """
        code_files = []
        
        for root, dirs, files in os.walk(self.project_path):
            # Filter directories
            dirs[:] = [
                d for d in dirs 
                if d not in self.excluded_dirs 
                and not d.startswith('.')
            ]
            
            for file in files:
                if file.startswith('.'):
                    continue
                
                file_path = Path(root) / file
                if file_path.suffix.lower() in self.code_extensions:
                    rel_path = file_path.relative_to(self.project_path)
                    code_files.append((file_path, str(rel_path)))
        
        return sorted(code_files, key=lambda x: x[1])
    
    def wait_between_messages(self, wait_time: int = None):
        """Wait between messages with a countdown"""
        if wait_time is None:
            wait_time = self.config['wait_time']
        
        self.logger.info(f"Waiting {wait_time} seconds before next message...")
        for i in range(wait_time, 0, -1):
            print(f"   ⏳ {i} seconds remaining...", end='\r')
            time.sleep(1)
        print("   " + " " * 30, end='\r')
        self.logger.info("Continuing...")
    
    def wait_for_response(self, timeout: int = 15) -> Optional[str]:
        """
        Wait for and get DeepSeek's response.
        
        Args:
            timeout: Maximum time to wait for response
            
        Returns:
            Response text or None if not found
        """
        try:
            time.sleep(3)
            
            # Wait for loading to complete
            self.wait_for_loading_complete(timeout)
            
            # Find the latest response
            for selector in self.chat_selectors['response']:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        latest = elements[-1]
                        if latest.is_displayed():
                            text = latest.text
                            if text and text.strip():
                                # Clean up the response
                                text = self.filter_bad_chars(text)
                                return text
                except:
                    continue
            
            # Try to get the last message from the chat
            try:
                messages = self.driver.find_elements(By.CSS_SELECTOR, '[class*="message"]')
                for msg in reversed(messages):
                    if msg.is_displayed():
                        text = msg.text
                        if text and text.strip():
                            return self.filter_bad_chars(text)
            except:
                pass
            
            return None
            
        except Exception as e:
            self.logger.warning(f"Error getting response: {e}")
            return None
    
    def introduce_project(self):
        """Main workflow to introduce the project to DeepSeek Chat"""
        self.logger.info("=" * 60)
        self.logger.info("PROJECT INTRODUCTION TO DEEPSEEK CHAT")
        self.logger.info("=" * 60)
        self.logger.info(f"Project: {self.project_path}")
        self.logger.info(f"Max File Size: {self.max_size} chars")
        self.logger.info(f"Wait Time: {self.config['wait_time']} seconds")
        self.logger.info("=" * 60)
        
        self.stats['start_time'] = datetime.now()
        
        # Step 1: Generate and send directory tree
        self.logger.info("Generating directory tree...")
        tree = self.get_directory_tree()
        self.logger.info("\n" + tree)
        
        # Send initial message with rules and tree
        initial_message = f"""I will show you my project structure. Here is the directory tree:
{tree}

IMPORTANT RULES:
1. For each file I send, just say "next file please" or "is there any other file"
2. Do NOT provide analysis or commentary on individual files
3. Only respond with "next file please" after each file
4. I will send files with the format: "File: filename" followed by the content
5. When you see "{self.finish_signal}", provide a comprehensive summary of the entire project

Let's begin."""
        
        self.logger.info("Sending initial message with rules...")
        if not self.send_message(initial_message):
            self.logger.error("Failed to send initial message")
            return
        
        # Wait for AI to acknowledge
        self.wait_between_messages(8)
        
        # Step 2: Send files one by one
        files = self.get_code_files()
        self.stats['total_files'] = len(files)
        
        self.logger.info(f"Found {len(files)} code files to send")
        
        if not files:
            self.logger.warning("No code files found in the project!")
            return
        
        # Send files in batches to avoid rate limiting
        for idx, (file_path, rel_path) in enumerate(files, 1):
            self.logger.info(f"Sending file {idx}/{len(files)}: {rel_path}")
            
            try:
                # Read file content
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Update stats
                self.stats['total_size'] += len(content)
                
                # Filter and truncate
                content = self.filter_bad_chars(content)
                if len(content) > self.max_size:
                    content = content[:self.max_size] + f"""
... [TRUNCATED: Original size {len(content)} chars, showing first {self.max_size}] ..."""
                
                # Prepare message
                file_extension = file_path.suffix.lower()
                lang = file_extension[1:] if file_extension else 'text'
                file_message = f"File: {rel_path}\n\n```{lang}\n{content}\n```"
                
                # Send the file
                if self.send_message(file_message):
                    self.processed_files.append(rel_path)
                    self.stats['sent_files'] += 1
                else:
                    self.stats['failed_files'] += 1
                    self.logger.warning(f"Failed to send file {rel_path}")
                    continue
                
                # Wait between files
                if idx < len(files):
                    self.wait_between_messages()
                
            except Exception as e:
                self.stats['failed_files'] += 1
                self.logger.error(f"Error processing file {rel_path}: {e}")
                continue
        
        # Step 3: Send finish signal and request summary
        self.logger.info("All files sent! Sending finish signal...")
        
        finish_message = f"""{self.finish_signal}

All {len(files)} files have been sent. Please provide a comprehensive summary of my project including:

1. **Project Overview**: What does this project do?
2. **Technology Stack**: Main languages, frameworks, and libraries used
3. **Architecture**: Project structure and design patterns
4. **Key Features**: Main functionality and purpose
5. **Code Quality**: Observations about code organization, readability, and best practices
6. **Dependencies**: Key dependencies and their purposes
7. **Improvements**: Potential improvements or next steps
8. **Questions**: Any questions you have about the project

After your summary, we can chat as real programmers about this project."""
        
        if self.send_message(finish_message):
            self.logger.info("Finish signal sent! Waiting for final summary...")
            
            self.logger.info("Waiting for DeepSeek to generate summary...")
            for i in range(self.config['summary_wait'], 0, -1):
                print(f"   📝 Generating summary... {i}s", end='\r')
                time.sleep(1)
            print("   " + " " * 40, end='\r')
            
            # Get final summary
            final_response = self.wait_for_response(timeout=self.config['timeout_response'])
            if final_response:
                self.logger.info("\n" + "=" * 60)
                self.logger.info("PROJECT SUMMARY FROM DEEPSEEK")
                self.logger.info("=" * 60)
                self.logger.info(final_response)
                self.logger.info("=" * 60)
                
                # Save summary to file
                summary_file = self.project_path / "PROJECT_SUMMARY_DEEPSEEK.md"
                with open(summary_file, 'w', encoding='utf-8') as f:
                    f.write(f"# AI-Generated Project Summary (DeepSeek)\n\n")
                    f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"**Project:** {self.project_path.name}\n")
                    f.write(f"**Files Analyzed:** {len(files)}\n")
                    f.write(f"**Total Size:** {self._format_size(self.stats['total_size'])}\n\n")
                    f.write("---\n\n")
                    f.write(final_response)
                self.logger.info(f"Summary saved to: {summary_file}")
            else:
                self.logger.warning("No final summary received")
        
        # Final statistics
        self.stats['end_time'] = datetime.now()
        duration = self.stats['end_time'] - self.stats['start_time']
        
        self.logger.info("\n" + "=" * 60)
        self.logger.info("PROJECT INTRODUCTION COMPLETE")
        self.logger.info("=" * 60)
        self.logger.info(f"Total Files: {self.stats['total_files']}")
        self.logger.info(f"Sent Files: {self.stats['sent_files']}")
        self.logger.info(f"Failed Files: {self.stats['failed_files']}")
        self.logger.info(f"Total Size: {self._format_size(self.stats['total_size'])}")
        self.logger.info(f"Duration: {duration.total_seconds():.1f} seconds")
        self.logger.info("=" * 60)
        self.logger.info("Ready for programming chat with DeepSeek!")
    
    def close(self):
        """Close the connection and cleanup"""
        if self.driver:
            try:
                self.driver.quit()
                self.logger.info("Connection closed")
            except:
                pass


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Project Introducer - Automatically introduce a project to DeepSeek Chat',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/project
  %(prog)s /path/to/project --port 9222 --wait 5
  %(prog)s /path/to/project --max-size 10000
  
Setup Instructions:
  1. Close all Chrome windows
  2. Start Chrome with remote debugging:
     chrome.exe --remote-debugging-port=9222 --user-data-dir="%TEMP%\\selenium-profile"
  3. Navigate to DeepSeek Chat (chat.deepseek.com) in Chrome
  4. Run this script with your project path
        """
    )
    
    parser.add_argument(
        'project_path',
        help='Path to the project directory'
    )
    
    parser.add_argument(
        '--port', '-p',
        type=int,
        default=9222,
        help='Chrome debugging port (default: 9222)'
    )
    
    parser.add_argument(
        '--max-size', '-m',
        type=int,
        default=5000,
        help='Max file size to send in characters (default: 5000)'
    )
    
    parser.add_argument(
        '--wait', '-w',
        type=int,
        default=10,
        help='Wait time between messages in seconds (default: 10)'
    )
    
    parser.add_argument(
        '--version', '-v',
        action='version',
        version=f'Project Introducer v{__version__}'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    try:
        args = parser.parse_args()
    except SystemExit:
        sys.exit(1)
    
    # Clean project path
    project_path = args.project_path.strip('"').strip("'")
    
    if project_path.startswith('~'):
        project_path = os.path.expanduser(project_path)
    
    # Validate path
    if not os.path.exists(project_path):
        print(f"❌ Error: Path does not exist: {project_path}")
        sys.exit(1)
    
    if not os.path.isdir(project_path):
        print(f"❌ Error: Path is not a directory: {project_path}")
        sys.exit(1)
    
    # Initialize and run
    introducer = ProjectIntroducer(
        project_path, 
        args.port, 
        args.max_size
    )
    introducer.config['wait_time'] = args.wait
    
    if args.debug:
        introducer.setup_logging(LogLevel.DEBUG)
    
    try:
        if not introducer.connect_to_chrome():
            sys.exit(1)
        
        introducer.introduce_project()
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        print("Exiting gracefully...")
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        introducer.close()


if __name__ == "__main__":
    main()