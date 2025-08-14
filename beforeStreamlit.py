

"""
JavaScript Error Capture Script using Playwright
Captures JS errors on websites by mimicking user interactions
Uses recursive exploration with XPath tracking and advanced blind interaction strategies
"""

import os
import random
import asyncio
import hashlib
from datetime import datetime
from urllib.parse import urlparse
from playwright.async_api import async_playwright

BASE_URL = "https://add-cwv-check--bbird--aemsites.aem.page/"
MAX_ACTIONS = 50  # limit for safety

visited_selectors = set()  # tracks visited element XPaths
seen_errors = set()  # tracks unique errors to prevent duplicates

# Global variables for enhanced navigation guard
current_element_info = None
navigation_in_progress = False
navigation_errors = []

# Global variable for single JSON error file
error_json_file = "error.json"

def initialize_error_json():
    """Initialize a fresh error.json file for each execution"""
    try:
        import json
        
        # Create fresh error data structure
        error_data = {
            "session_info": {
                "timestamp": datetime.now().isoformat(),
                "base_url": BASE_URL,
                "script_name": "js_error_capture.py",
                "execution_start": datetime.now().isoformat()
            },
            "errors": []
        }
        
        # Write fresh file
        with open(error_json_file, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, indent=2, ensure_ascii=False)
        
        print(f"🔄 Fresh error.json file initialized for new execution")
        
    except Exception as e:
        print(f"❌ Failed to initialize error.json: {e}")

async def get_code_context_from_location(page, file_url, line_number):
    """Get code context using Playwright's msg.location() API to get exact file URLs"""
    try:
        print(f"🔍 Fetching code from URL: {file_url}")
        print(f"📍 Line number: {line_number}")
        
        # Use Playwright's evaluate to fetch the file directly
        source_code = await page.evaluate("""
            async (fileUrl) => {
                try {
                    console.log('Fetching file:', fileUrl);
                    const response = await fetch(fileUrl);
                    if (response.ok) {
                        const text = await response.text();
                        console.log('Successfully fetched', text.length, 'characters');
                        return text;
                    } else {
                        console.log('Fetch failed with status:', response.status);
                        return null;
                    }
                } catch (error) {
                    console.log('Fetch error:', error.message);
                    return null;
                }
            }
        """, file_url)
        
        if source_code:
            print(f"✅ Successfully fetched source code ({len(source_code)} chars)")
            return await extract_code_context(source_code, file_url, line_number)
        else:
            print(f"❌ Failed to fetch source code from {file_url}")
            return None
                
    except Exception as e:
        print(f"Error getting code context from location: {e}")
        return None

async def extract_code_context(source_code, filename, line_number):
    """Extract code context from source code - 30 lines before/after error line"""
    try:
        lines = source_code.split('\n')
        start_line = max(0, line_number - 31)
        end_line = min(len(lines) - 1, line_number + 29)
        
        print(f"📄 Successfully extracted code context for {filename} at line {line_number}")
        print(f"   Context: lines {start_line + 1} to {end_line + 1} (error at line {line_number})")
        
        context_string = ""
        for i in range(start_line, end_line + 1):
            line_content = lines[i] if i < len(lines) else ''
            is_error_line = i == line_number - 1
            marker = ">>> " if is_error_line else "    "
            context_string += f"{marker}{line_content}\n"
        
        return context_string.strip()
    except Exception as e:
        print(f"Error extracting code context: {e}")
        return None

def save_error_to_json(error_detail):
    """Save error to single JSON file in real-time"""
    try:
        import json
        
        # Load existing errors or create new structure
        try:
            with open(error_json_file, 'r', encoding='utf-8') as f:
                error_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            # If file doesn't exist or is corrupted, create fresh structure
            error_data = {
                "session_info": {
                    "timestamp": datetime.now().isoformat(),
                    "base_url": BASE_URL,
                    "script_name": "js_error_capture.py"
                },
                "errors": []
            }
        
        # Add new error to the list
        error_data["errors"].append(error_detail)
        
        # Update session info
        error_data["session_info"]["last_updated"] = datetime.now().isoformat()
        error_data["session_info"]["total_errors"] = len(error_data["errors"])
        
        # Save back to file
        with open(error_json_file, 'w', encoding='utf-8') as f:
            json.dump(error_data, f, indent=2, ensure_ascii=False)
        
        print(f"💾 Error saved to {error_json_file} (Total: {len(error_data['errors'])})")
        
    except Exception as e:
        print(f"❌ Failed to save error to JSON: {e}")


def generate_error_signature(error_type, error_message, filename=None, lineno=None, colno=None):
    """Generate a unique signature for an error to enable deduplication"""
    # Create a signature based on error message and location (ignore error_type for deduplication)
    # This ensures the same error doesn't get captured multiple times even if it's detected by different handlers
    signature_parts = [
        error_message[:200] if error_message else "",  # Limit message length but keep more context
        filename or "",
        str(lineno) if lineno else "",
        str(colno) if colno else ""
    ]
    
    # Create a hash of the signature parts
    signature_string = "|".join(signature_parts)
    return hashlib.md5(signature_string.encode('utf-8')).hexdigest()


async def handle_error(page, filename, err, error_type="unknown", error_details=None):
    """Handle errors by saving to JSON file with enhanced error information and deduplication"""
    try:
        # Generate error signature for deduplication
        error_message = str(err)
        filename_info = error_details.get('filename', 'Unknown') if error_details else 'Unknown'
        lineno_info = error_details.get('lineno', 'Unknown') if error_details else 'Unknown'
        colno_info = error_details.get('colno', 'Unknown') if error_details else 'Unknown'
        
        error_signature = generate_error_signature(
            error_type, 
            error_message, 
            filename_info, 
            lineno_info, 
            colno_info
        )
        
        # Check if we've seen this error before
        if error_signature in seen_errors:
            print(f"🔄 Duplicate error skipped: {error_type} - {error_message[:50]}...")
            return
        
        # Additional check: Look for similar errors in the JSON file to prevent duplicates
        try:
            import json
            try:
                with open(error_json_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                
                # Check if this exact error already exists
                for existing_error in existing_data.get("errors", []):
                    existing_message = existing_error.get("error_message", "")
                    existing_filename = existing_error.get("filename", "")
                    existing_line = existing_error.get("line_number", "")
                    
                    # If same message, filename, and line number, it's a duplicate
                    if (existing_message == error_message and 
                        existing_filename == filename_info and 
                        existing_line == lineno_info):
                        print(f"🔄 Duplicate error found in JSON: {error_type} - {error_message[:50]}...")
                        return
                        
            except (FileNotFoundError, json.JSONDecodeError):
                pass  # File doesn't exist or is corrupted, continue
        except Exception as e:
            print(f"⚠️ Error checking for duplicates: {e}")
        
        # Add to seen errors set
        seen_errors.add(error_signature)
        
        print(f"🚨 {error_type.upper()} Error captured: {err}")
        print(f"🆔 Error Signature: {error_signature[:8]}...")
        
        # Create timestamp for error tracking
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Store detailed error information for JSON export
        error_detail = {
            "error_signature": error_signature,
            "error_type": error_type,
            "error_message": str(err),
            "timestamp": datetime.now().isoformat(),
            "url": page.url,
            "filename": filename_info,
            "line_number": lineno_info,
            "column_number": colno_info,
            "error_log_file": None  # Will be set after creating the log file
        }
        
        # Add additional error details if available
        if error_details:
            error_detail.update(error_details)
        
        # Save error to single JSON file immediately
        save_error_to_json(error_detail)
        
        # Error is already saved to JSON file above
        print(f"📝 Error details saved to {error_json_file}")
        
        # Print enhanced error info to console
        print(f"📄 File: {filename_info}")
        print(f"📍 Line: {lineno_info}")
        print(f"📍 Column: {colno_info}")
        
        # Show click context if available
        if error_details and 'clickEventCount' in error_details:
            print(f"🖱️ Click Context: Event #{error_details['clickEventCount']} at {error_details.get('lastClickTime', 'Unknown')}")
            if 'clickContext' in error_details:
                click_ctx = error_details['clickContext']
                time_since = click_ctx.get('timeSinceClick', 0)
                print(f"⏱️ Time since click: {time_since}ms")
        
        if error_details and ('stack' in error_details or 'stackTrace' in error_details):
            stack_trace = error_details.get('stack') or error_details.get('stackTrace')
            print(f"📚 Stack Trace: {stack_trace[:200]}..." if len(str(stack_trace)) > 200 else f"📚 Stack Trace: {stack_trace}")
        
    except Exception as e:
        print(f"❌ Failed to capture error: {e}")


class AdvancedBlindInteractionStrategy:
    """Advanced blind interaction strategy with recursive exploration"""
    
    def __init__(self, page):
        self.page = page
        self.interaction_history = []
        self.discovered_elements = set()
        self.actions_performed = 0
        
    async def discover_interactive_elements(self):
        """Dynamically discover all potentially interactive elements"""
        print("🔍 Discovering interactive elements...")
        
        # Comprehensive selectors for interactive elements
        interactive_selectors = [
            # Links and navigation
            "a[href]", "a[role='button']", "a[tabindex]",
            
            # Buttons and form controls
            "button", "input[type='submit']", "input[type='button']", 
            "input[type='reset']", "[role='button']", "[tabindex]",
            
            # Form inputs
            "input[type='text']", "input[type='email']", "input[type='search']",
            "input[type='password']", "input[type='number']", "input[type='tel']",
            "input:not([type])", "textarea", "select",
            
            # Interactive components
            "[onclick]", "[onchange]", "[onsubmit]", "[onfocus]", "[onblur]",
            "[data-action]", "[data-toggle]", "[data-target]",
            
            # Custom interactive elements
            ".btn", ".button", ".clickable", ".interactive",
            "[class*='btn']", "[class*='button']", "[class*='click']",
            
            # ARIA interactive elements
            "[aria-label]", "[aria-describedby]", "[aria-controls]",
            "[aria-expanded]", "[aria-selected]", "[aria-checked]",
            
            # Modern web components
            "[data-testid]", "[data-cy]", "[data-qa]",
            "[class*='card']", "[class*='item']", "[class*='product']",
            
            # Generic clickable patterns
            "[style*='cursor: pointer']", "[style*='cursor:pointer']",
            "[class*='hover']", "[class*='active']", "[class*='focus']"
        ]
        
        all_elements = []
        for selector in interactive_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                for element in elements:
                    # Check if element is actually visible and interactive
                    try:
                        is_visible = await element.is_visible()
                        if is_visible:
                            # Get element info for logging
                            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                            element_id = await element.evaluate("el => el.id || ''")
                            element_class = await element.evaluate("el => el.className || ''")
                            
                            element_info = {
                                'element': element,
                                'selector': selector,
                                'tag_name': tag_name,
                                'id': element_id,
                                'class': element_class,
                                'interaction_type': self._determine_interaction_type(selector, tag_name)
                            }
                            
                            all_elements.append(element_info)
                    except:
                        continue
            except:
                continue
        
        print(f"✅ Discovered {len(all_elements)} interactive elements")
        return all_elements
    
    def _determine_interaction_type(self, selector, tag_name):
        """Determine the best interaction method for an element"""
        if 'input' in selector or tag_name in ['input', 'textarea', 'select']:
            return 'input'
        elif 'button' in selector or tag_name == 'button':
            return 'click'
        elif 'a[href]' in selector or tag_name == 'a':
            return 'click'
        else:
            return 'click'
    
    async def intelligent_interaction(self, element_info):
        """Perform intelligent interaction based on element type"""
        element = element_info['element']
        interaction_type = element_info['interaction_type']
        
        try:
            # Scroll element into view
            await element.scroll_into_view_if_needed()
            await asyncio.sleep(0.2)
            
            if interaction_type == 'input':
                await self._handle_input_interaction(element, element_info)
            else:
                await self._handle_click_interaction(element, element_info)
                
        except Exception as e:
            print(f"❌ Failed to interact with {element_info['tag_name']}: {e}")
    
    async def _handle_input_interaction(self, element, element_info):
        """Handle input field interactions intelligently with dropdown testing"""
        try:
            # Get input type and current value
            input_type = await element.evaluate("el => el.type || 'text'")
            current_value = await element.evaluate("el => el.value || ''")
            
            print(f"✏️ Testing input field: {input_type} (ID: {element_info['id']}, Class: {element_info['class']})")
            
            # Focus on the input first
            await element.click()
            await element.focus()
            await asyncio.sleep(0.5)
            
            # Test 1: Single character input to trigger dropdown
            print(f"🔤 Typing single character to trigger dropdown...")
            await element.fill("a")
            await asyncio.sleep(2.0)  # Wait longer for dropdown to appear
            
            # Look for dropdown suggestions
            dropdown_elements = await self._find_dropdown_suggestions()
            if dropdown_elements:
                print(f"📋 Found {len(dropdown_elements)} dropdown suggestions")
                
                # Test clicking each dropdown suggestion
                for i, suggestion in enumerate(dropdown_elements):
                    try:
                        suggestion_text = await suggestion.evaluate("el => el.textContent?.trim() || el.innerText?.trim() || 'No text'")
                        print(f"🖱️ Clicking dropdown suggestion {i+1}: {suggestion_text[:50]}...")
                        
                        # Click the suggestion
                        await suggestion.click()
                        await asyncio.sleep(1.5)  # Wait for selection to complete
                        
                        # Clear and try again for next suggestion
                        if i < len(dropdown_elements) - 1:  # Don't clear after last suggestion
                            await element.click()
                            await element.fill("a")
                            await asyncio.sleep(2.0)  # Wait for dropdown to reappear
                            
                            # Get fresh dropdown elements
                            new_dropdown = await self._find_dropdown_suggestions()
                            if new_dropdown and len(new_dropdown) > i + 1:
                                suggestion = new_dropdown[i + 1]  # Get next suggestion
                            else:
                                break  # No more suggestions
                        
                    except Exception as e:
                        print(f"❌ Failed to click dropdown suggestion {i+1}: {e}")
                        break
            else:
                print(f"📋 No dropdown suggestions found for this input")
            
            # Test 2: Different characters to see if they trigger different suggestions
            test_chars = ["b", "c", "1", "test"]
            for char in test_chars:
                try:
                    await element.click()
                    await element.fill("")
                    await element.type(char, delay=100)
                    await asyncio.sleep(2.0)  # Wait for dropdown
                    
                    # Check for new dropdown
                    new_dropdown = await self._find_dropdown_suggestions()
                    if new_dropdown:
                        print(f"📋 Found {len(new_dropdown)} suggestions for '{char}'")
                        
                        # Click first suggestion if available
                        if len(new_dropdown) > 0:
                            suggestion_text = await new_dropdown[0].evaluate("el => el.textContent?.trim() || el.innerText?.trim() || 'No text'")
                            print(f"🖱️ Clicking first suggestion for '{char}': {suggestion_text[:50]}...")
                            await new_dropdown[0].click()
                            await asyncio.sleep(1.5)
                    
                except Exception as e:
                    print(f"❌ Failed to test character '{char}': {e}")
            
            # Test 3: Full text input
            test_text = f"test input {random.randint(100, 999)}"
            try:
                await element.click()
                await element.fill("")
                await element.type(test_text, delay=50)
                await asyncio.sleep(1)
                
                # Trigger events
                await element.press("Tab")
                await element.press("Enter")
                await asyncio.sleep(1)
                
            except Exception as e:
                print(f"❌ Failed to test full text: {e}")
            
            print(f"✅ Input field testing complete for {input_type}")
            
        except Exception as e:
            print(f"❌ Input interaction failed: {e}")
    
    async def _find_dropdown_suggestions(self):
        """Find dropdown suggestion elements that commonly appear after typing"""
        dropdown_selectors = [
            # Common dropdown suggestion selectors
            ".dropdown", ".suggestions", ".autocomplete", ".options",
            "[role='listbox']", "[role='option']", "[aria-expanded='true']",
            ".suggestion", ".option", ".item", ".result",
            "[class*='dropdown']", "[class*='suggestion']", "[class*='autocomplete']",
            "[class*='option']", "[class*='item']", "[class*='result']",
            # More specific patterns
            "ul[class*='suggestion']", "li[class*='suggestion']",
            "div[class*='dropdown']", "div[class*='suggestion']",
            "span[class*='suggestion']", "a[class*='suggestion']"
        ]
        
        all_suggestions = []
        for selector in dropdown_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                for element in elements:
                    try:
                        if await element.is_visible():
                            all_suggestions.append(element)
                    except:
                        continue
            except:
                continue
        
        return all_suggestions
    
    async def _handle_click_interaction(self, element, element_info):
        """Handle click interactions intelligently"""
        try:
            # Check if element is actually clickable
            is_enabled = await element.evaluate("el => !el.disabled && el.offsetParent !== null")
            
            if not is_enabled:
                return
            
            # Perform the click
            await element.click(timeout=3000)
            
            # Log the interaction
            element_text = await element.evaluate("el => el.textContent?.trim() || el.innerText?.trim() || 'No text'")
            print(f"🖱️ Clicked {element_info['tag_name']}: {element_text[:30]}...")
            
            # Wait for potential page changes or errors
            await asyncio.sleep(1)
            
        except Exception as e:
            print(f"❌ Click interaction failed: {e}")
    
    def _generate_test_data(self, input_type):
        """Generate appropriate test data for different input types"""
        if input_type in ['email', 'text']:
            return f"test{random.randint(1000, 9999)}@example.com"
        elif input_type == 'password':
            return f"TestPass{random.randint(100, 999)}!"
        elif input_type == 'number':
            return str(random.randint(1, 100))
        elif input_type == 'tel':
            return f"+1{random.randint(1000000000, 9999999999)}"
        elif input_type == 'search':
            return f"test search {random.randint(1, 100)}"
        else:
            return f"test{random.randint(1000, 9999)}"
    
    async def test_input_fields_specifically(self):
        """Specifically test input fields for dropdown functionality and errors"""
        print("🔍 Starting specific input field testing for dropdowns...")
        
        # Find all input fields
        input_selectors = [
            "input[type='text']", "input[type='search']", "input[type='email']",
            "input:not([type])", "textarea", "input[type='tel']", "input[type='number']"
        ]
        
        all_inputs = []
        for selector in input_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                for element in elements:
                    try:
                        if await element.is_visible():
                            # Get element info
                            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                            element_id = await element.evaluate("el => el.id || ''")
                            element_class = await element.evaluate("el => el.className || ''")
                            
                            input_info = {
                                'element': element,
                                'selector': selector,
                                'tag_name': tag_name,
                                'id': element_id,
                                'class': element_class
                            }
                            all_inputs.append(input_info)
                    except:
                        continue
            except:
                continue
        
        print(f"📝 Found {len(all_inputs)} input fields to test")
        
        # Test each input field thoroughly
        for i, input_info in enumerate(all_inputs):
            try:
                print(f"\n🔍 Testing input field {i+1}/{len(all_inputs)}: {input_info['tag_name']} (ID: {input_info['id']})")
                
                element = input_info['element']
                
                # Scroll into view
                await element.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                
                # Focus and clear
                await element.click()
                await element.focus()
                await element.fill("")
                await asyncio.sleep(0.5)
                
                # Test 1: Single character to trigger dropdown
                print(f"🔤 Typing 'a' to trigger dropdown...")
                await element.type("a", delay=100)
                await asyncio.sleep(2.5)  # Wait longer for dropdown
                
                # Look for dropdown
                dropdown_elements = await self._find_dropdown_suggestions()
                if dropdown_elements:
                    print(f"📋 Found {len(dropdown_elements)} dropdown suggestions")
                    
                    # Test clicking each suggestion systematically
                    for j, suggestion in enumerate(dropdown_elements):
                        try:
                            suggestion_text = await suggestion.evaluate("el => el.textContent?.trim() || el.innerText?.trim() || 'No text'")
                            print(f"🖱️ Clicking suggestion {j+1}: {suggestion_text[:50]}...")
                            
                            # Click the suggestion
                            await suggestion.click()
                            await asyncio.sleep(2.0)  # Wait for selection to complete
                            
                            # Clear and try again for next suggestion
                            if j < len(dropdown_elements) - 1:  # Don't clear after last suggestion
                                await element.click()
                                await element.fill("")
                                await element.type("a", delay=100)
                                await asyncio.sleep(2.5)  # Wait for dropdown to reappear
                                
                                # Get fresh dropdown elements
                                new_dropdown = await self._find_dropdown_suggestions()
                                if new_dropdown and len(new_dropdown) > j + 1:
                                    suggestion = new_dropdown[j + 1]  # Get next suggestion
                                else:
                                    break  # No more suggestions
                            
                        except Exception as e:
                            print(f"❌ Failed to test suggestion {j+1}: {e}")
                            break
                else:
                    print(f"📋 No dropdown suggestions found")
                
                # Test 2: Different characters
                test_chars = ["b", "c", "1", "test"]
                for char in test_chars:
                    try:
                        await element.click()
                        await element.fill("")
                        await element.type(char, delay=100)
                        await asyncio.sleep(2.5)  # Wait longer for dropdown
                        
                        # Check for new dropdown
                        new_dropdown = await self._find_dropdown_suggestions()
                        if new_dropdown:
                            print(f"📋 Found {len(new_dropdown)} suggestions for '{char}'")
                            
                            # Click first suggestion if available
                            if len(new_dropdown) > 0:
                                suggestion_text = await new_dropdown[0].evaluate("el => el.textContent?.trim() || el.innerText?.trim() || 'No text'")
                                print(f"🖱️ Clicking first suggestion for '{char}': {suggestion_text[:50]}...")
                                await new_dropdown[0].click()
                                await asyncio.sleep(2.0)  # Wait for selection
                        
                    except Exception as e:
                        print(f"❌ Failed to test character '{char}': {e}")
                
                # Test 3: Full text input
                test_text = f"test input {random.randint(100, 999)}"
                try:
                    await element.click()
                    await element.fill("")
                    await element.type(test_text, delay=50)
                    await asyncio.sleep(1)
                    
                    # Trigger events
                    await element.press("Tab")
                    await element.press("Enter")
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    print(f"❌ Failed to test full text: {e}")
                
                print(f"✅ Input field {i+1} testing complete")
                
            except Exception as e:
                print(f"❌ Failed to test input field {i+1}: {e}")
            
            # Wait between inputs
            await asyncio.sleep(1)
        
        print(f"🎯 Input field testing complete for {len(all_inputs)} fields")
    
    async def recursive_monkey_exploration(self, actions_done=0):
        """Recursive exploration with XPath tracking and intelligent interactions"""
        if actions_done >= MAX_ACTIONS:
            print(f"🛑 Reached max actions ({MAX_ACTIONS}). Stopping.")
            return
        
        print(f"🔄 Recursive exploration step {actions_done + 1}/{MAX_ACTIONS}")
        
        # Discover current interactive elements
        all_elements = await self.discover_interactive_elements()
        
        if not all_elements:
            print("❌ No interactive elements found.")
            return
        
        # Filter out already visited elements using XPath
        unvisited_elements = []
        for element_info in all_elements:
            try:
                xpath = await get_xpath(element_info['element'])
                if xpath not in visited_selectors:
                    unvisited_elements.append((element_info, xpath))
            except:
                continue
        
        if not unvisited_elements:
            print("✅ All elements have been visited. Exploration complete.")
            return
        
        # Pick a random unvisited element
        element_info, xpath = random.choice(unvisited_elements)
        visited_selectors.add(xpath)
        
        print(f"🎯 Interacting with new element: {xpath}")
        
        try:
            # Perform intelligent interaction
            await self.intelligent_interaction(element_info)
            self.actions_performed += 1
            
            # Wait for possible navigation or DOM changes
            try:
                await self.page.wait_for_load_state("domcontentloaded", timeout=3000)
            except:
                pass
            
            # Random delay between actions
            delay = random.uniform(0.5, 2.0)
            print(f"⏳ Waiting {delay:.1f}s before next action...")
            await asyncio.sleep(delay)
            
        except Exception as e:
            print(f"❌ Interaction failed: {e}")
        
        # Recurse for next action
        await self.recursive_monkey_exploration(actions_done + 1)
    
    async def stress_test_interactions(self, duration_seconds=15):
        """Stress test with rapid interactions to trigger edge cases"""
        print(f"💥 Starting stress test for {duration_seconds} seconds...")
        
        start_time = asyncio.get_event_loop().time()
        interactions = 0
        
        while (asyncio.get_event_loop().time() - start_time) < duration_seconds:
            try:
                # Get current interactive elements
                elements = await self.discover_interactive_elements()
                if not elements:
                    break
                
                # Pick random element and interact
                element_info = random.choice(elements)
                await self.intelligent_interaction(element_info)
                
                interactions += 1
                await asyncio.sleep(0.2)  # Very fast interactions
                
            except Exception as e:
                print(f"❌ Stress test interaction failed: {e}")
        
        print(f"💥 Stress test complete. Performed {interactions} rapid interactions.")

    async def click_all_links_and_buttons(self):
        """Click all links and buttons on the page to trigger console errors"""
        print("🔄 Clicking all links and buttons to capture console errors...")
        
        # Store the original URL to ensure we stay within the target domain
        original_url = self.page.url
        target_domain = self._extract_domain(original_url)
        print(f"🎯 Target domain: {target_domain}")
        
        # Store original page state for comparison
        original_page_state = await self._capture_page_state()
        print(f"📄 Original page state captured")
        
        # Set up JavaScript navigation monitoring
        await self.page.add_init_script("""
            // Monitor for JavaScript-based navigation
            let navigationEvents = [];
            
            // Track pushState/replaceState calls (SPA navigation)
            const originalPushState = history.pushState;
            const originalReplaceState = history.replaceState;
            
            history.pushState = function(...args) {
                navigationEvents.push({
                    type: 'pushState',
                    url: args[2],
                    timestamp: new Date().toISOString()
                });
                return originalPushState.apply(this, args);
            };
            
            history.replaceState = function(...args) {
                navigationEvents.push({
                    type: 'replaceState',
                    url: args[2],
                    timestamp: new Date().toISOString()
                });
                return originalReplaceState.apply(this, args);
            };
            
            // Track hash changes
            window.addEventListener('hashchange', function(event) {
                navigationEvents.push({
                    type: 'hashchange',
                    oldURL: event.oldURL,
                    newURL: event.newURL,
                    timestamp: new Date().toISOString()
                });
            });
            
            // Expose navigation events to Python
            window.getNavigationEvents = function() {
                const events = [...navigationEvents];
                navigationEvents = []; // Clear after reading
                return events;
            };
        """)

        # Focus on clickable elements first (links, buttons, clickable divs)
        clickable_selectors = [
            # Primary clickable elements
            "a[href]", "button", "input[type='submit']", "input[type='button']",
            "[role='button']", "[onclick]", "[data-action]", "[data-toggle]",
            
            # Interactive components
            ".btn", ".button", ".clickable", ".interactive", ".nav-link",
            "[class*='btn']", "[class*='button']", "[class*='click']",
            "[class*='nav']", "[class*='menu']", "[class*='tab']",
            
            # Modern web components
            "[data-testid]", "[data-cy]", "[data-qa]", "[data-target]",
            "[class*='card']", "[class*='item']", "[class*='product']",
            
            # Generic clickable patterns
            "[style*='cursor: pointer']", "[style*='cursor:pointer']",
            "[class*='hover']", "[class*='active']", "[class*='focus']"
        ]
        
        all_clickable_elements = []
        for selector in clickable_selectors:
            try:
                elements = await self.page.query_selector_all(selector)
                for element in elements:
                    try:
                        if await element.is_visible():
                            # Get element info
                            tag_name = await element.evaluate("el => el.tagName.toLowerCase()")
                            element_id = await element.evaluate("el => el.id || ''")
                            element_class = await element.evaluate("el => el.className || ''")
                            element_text = await element.evaluate("el => el.textContent?.trim() || el.innerText?.trim() || 'No text'")
                            
                            # For links, check if they're external or internal
                            href = None
                            is_external = False
                            if tag_name == 'a':
                                href = await element.evaluate("el => el.href || ''")
                                is_external = self._is_external_link(href, target_domain)
                            
                            element_info = {
                                'element': element,
                                'selector': selector,
                                'tag_name': tag_name,
                                'id': element_id,
                                'class': element_class,
                                'text': element_text[:50] + "..." if len(element_text) > 50 else element_text,
                                'href': href,
                                'is_external': is_external
                            }
                            
                            all_clickable_elements.append(element_info)
                    except:
                        continue
            except:
                continue
        
        print(f"🎯 Found {len(all_clickable_elements)} clickable elements to test")
        
        # Track clicked elements to avoid duplicates using stable DOM paths
        clicked_elements = set()
        
        for i, element_info in enumerate(all_clickable_elements):
            try:
                # Generate stable DOM path for duplicate detection
                element_path = await self._get_stable_dom_path(element_info['element'])
                
                if element_path in clicked_elements:
                    print(f"🔄 Skipping duplicate element: {element_info['text']}")
                    continue
                
                clicked_elements.add(element_path)
                
                # Skip external links that would navigate away from our target site
                if element_info['is_external']:
                    print(f"🌐 Skipping external link: {element_info['text']} -> {element_info['href']}")
                    continue
                
                # Check if link opens in new tab/window
                if tag_name == 'a':
                    target_attr = await element_info['element'].evaluate("el => el.target || ''")
                    if target_attr in ['_blank', '_new', '_top']:
                        print(f"🔄 Skipping link that opens in new tab/window: {element_info['text']}")
                        continue
                
                print(f"\n🖱️ Clicking element {i+1}/{len(all_clickable_elements)}: {element_info['tag_name']} - {element_info['text']}")
                
                # Scroll into view
                await element_info['element'].scroll_into_view_if_needed()
                await asyncio.sleep(0.3)
                
                # Check if element is still clickable
                try:
                    is_enabled = await element_info['element'].evaluate("el => !el.disabled && el.offsetParent !== null")
                    if not is_enabled:
                        print(f"⚠️ Element not clickable, skipping: {element_info['text']}")
                        continue
                except:
                    pass
                
                # Store current URL before clicking
                current_url = self.page.url
                
                # Set current element info for navigation context
                global current_element_info
                current_element_info = element_info
                
                # Perform the click
                await element_info['element'].click(timeout=5000)
                print(f"✅ Clicked: {element_info['text']}")
                
                # Wait for potential navigation or DOM changes
                try:
                    await self.page.wait_for_load_state("domcontentloaded", timeout=3000)
                except:
                    pass
                
                # Check if we navigated to a different page
                new_url = self.page.url
                if new_url != current_url:
                    print(f"🔄 Page navigated from {current_url} to {new_url}")
                    
                    # Check if we're still within our target domain
                    if not self._is_same_domain(new_url, target_domain):
                        print(f"⚠️ Navigated outside target domain! Returning to original site...")
                        # Navigate back to the original site
                        await self.page.goto(original_url, wait_until="domcontentloaded")
                        print(f"🏠 Returned to original site: {original_url}")
                    else:
                        print(f"✅ Still within target domain: {self._extract_domain(new_url)}")
                        # Update our current context but keep original URL for reference
                        current_url = new_url
                
                # Also check for JavaScript-based navigation (SPA routing)
                try:
                    # Check if the page title or main content changed significantly
                    new_title = await self.page.title()
                    main_content = await self.page.evaluate("""
                        () => {
                            const main = document.querySelector('main') || 
                                        document.querySelector('#main') || 
                                        document.querySelector('.main') ||
                                        document.querySelector('article') ||
                                        document.querySelector('.content');
                            return main ? main.textContent.trim().substring(0, 100) : '';
                        }
                    """)
                    
                    # If content changed significantly, we might be on a different page
                    if main_content and len(main_content) > 20:
                        print(f"📄 Content changed: {main_content[:50]}...")
                        
                        # Check if we should return to original site based on content
                        if self._should_return_to_original(main_content, target_domain):
                            print(f"⚠️ Content suggests we're on a different site. Returning to original...")
                            await self.page.goto(original_url, wait_until="domcontentloaded")
                            print(f"🏠 Returned to original site: {original_url}")
                        
                        # Also compare with original page state
                        current_page_state = {
                            "title": new_title,
                            "url": self.page.url,
                            "main_content": main_content
                        }
                        
                        if self._has_significantly_changed(original_page_state, current_page_state):
                            print(f"🔄 Page state significantly changed - might be on different site")
                            # Check if we should return to original
                            if self._should_return_based_on_state_change(original_page_state, current_page_state):
                                print(f"⚠️ Returning to original site due to significant state change...")
                                await self.page.goto(original_url, wait_until="domcontentloaded")
                                print(f"🏠 Returned to original site: {original_url}")
                except Exception as e:
                    # If we can't check content, continue
                    pass
                
                # Wait for any console errors to be captured
                await asyncio.sleep(1)
                
                # Check for JavaScript-based navigation events
                try:
                    js_navigation_events = await self.page.evaluate("window.getNavigationEvents()")
                    if js_navigation_events and len(js_navigation_events) > 0:
                        print(f"🔄 JavaScript navigation detected: {len(js_navigation_events)} events")
                        for event in js_navigation_events:
                            print(f"   - {event['type']}: {event.get('url', event.get('newURL', 'N/A'))}")
                        
                        # If we have significant navigation, check if we should return
                        if any(event['type'] in ['pushState', 'replaceState'] for event in js_navigation_events):
                            print(f"⚠️ SPA navigation detected - checking if we should return to original...")
                            # Wait a bit for the navigation to complete
                            await asyncio.sleep(1)
                            
                            # Check current page state
                            current_state = await self._capture_page_state()
                            if self._should_return_based_on_state_change(original_page_state, current_state):
                                print(f"⚠️ Returning to original site due to SPA navigation...")
                                await self.page.goto(original_url, wait_until="domcontentloaded")
                                print(f"🏠 Returned to original site: {original_url}")
                except Exception as e:
                    # If we can't check navigation events, continue
                    pass
                
                # Random delay between clicks
                delay = random.uniform(0.8, 2.5)
                print(f"⏳ Waiting {delay:.1f}s before next click...")
                await asyncio.sleep(delay)
                
            except Exception as e:
                print(f"❌ Failed to click element {i+1}: {e}")
                continue
        
        print(f"\n✅ Clicking phase complete! Successfully clicked {len(clicked_elements)} unique elements")
        print("🔍 Console errors should now be captured from all clickable elements")
        
        # Return summary for main function
        return {
            'total_elements_found': len(all_clickable_elements),
            'successfully_clicked': len(clicked_elements),
            'clicked_elements': list(clicked_elements)
        }
    
    async def _get_stable_dom_path(self, element):
        """Generate a stable DOM path for duplicate detection"""
        try:
            return await element.evaluate("""
                (el) => {
                    const seg = e => {
                        if (!e || e.nodeType !== 1) return '';
                        let s = e.nodeName.toLowerCase();
                        if (e.id) return s + '#' + e.id;
                        const cls = (e.className || '').toString().trim().split(/\\s+/).filter(Boolean);
                        if (cls.length) s += '.' + cls.slice(0, 3).join('.');
                        const parent = e.parentElement;
                        if (!parent) return s;
                        const sibs = Array.from(parent.children).filter(n => n.nodeName === e.nodeName);
                        if (sibs.length > 1) s += `:nth-of-type(${sibs.indexOf(e)+1})`;
                        return s;
                    };
                    const parts = [];
                    let cur = el;
                    for (let i = 0; i < 8 && cur; i++) {
                        parts.unshift(seg(cur));
                        cur = cur.parentElement;
                    }
                    return parts.join(' > ');
                }
            """)
        except:
            # Fallback to a simple identifier
            return f"element_{id(element)}"
    
    def _extract_domain(self, url):
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return url
    
    def _is_external_link(self, href, target_domain):
        """Check if a link is external to our target domain"""
        if not href or not target_domain:
            return False
        
        try:
            from urllib.parse import urlparse
            parsed = urlparse(href)
            link_domain = parsed.netloc
            
            # If no domain in href, it's internal
            if not link_domain:
                return False
            
            # Check if it's the same domain
            return link_domain != target_domain
        except:
            return False
    
    def _is_same_domain(self, url, target_domain):
        """Check if a URL is within the same domain"""
        if not url or not target_domain:
            return False
        
        current_domain = self._extract_domain(url)
        return current_domain == target_domain

    def _should_return_to_original(self, current_content, target_domain):
        """Determine if the current page content suggests a navigation outside the target domain."""
        # Simple heuristic: if content is very different, we might be on a different site
        # This is a basic check that can be refined based on actual needs
        
        # For now, we'll use a simple approach:
        # - If content is empty or very short, stay (might be loading)
        # - If content is very long and different, might be a different site
        
        if not current_content or len(current_content) < 10:
            return False  # Content is loading or minimal, stay
        
        # Check for common indicators of external sites
        external_indicators = [
            'login', 'sign in', 'sign up', 'register', 'password',
            'facebook', 'twitter', 'google', 'microsoft', 'apple',
            'amazon', 'ebay', 'paypal', 'stripe', 'checkout',
            '404', 'not found', 'error', 'access denied'
        ]
        
        current_lower = current_content.lower()
        for indicator in external_indicators:
            if indicator in current_lower:
                print(f"🔍 Detected external indicator: {indicator}")
                return True
        
        return False

    async def _capture_page_state(self):
        """Captures the current state of the page (title, URL, main content) for comparison."""
        page_state = {
            "title": await self.page.title(),
            "url": self.page.url,
            "main_content": await self.page.evaluate("""
                () => {
                    const main = document.querySelector('main') || 
                                document.querySelector('#main') || 
                                document.querySelector('.main') ||
                                document.querySelector('article') ||
                                document.querySelector('.content');
                    return main ? main.textContent.trim().substring(0, 100) : '';
                }
            """)
        }
        return page_state

    def _has_significantly_changed(self, original_state, current_state):
        """Determine if the current page state has significantly changed from the original."""
        # This is a placeholder heuristic. In a real scenario, you'd compare
        # more granular aspects of the page state, e.g., title, URL, main content.
        # For simplicity, we'll check if the title or URL has changed.
        return original_state['title'] != current_state['title'] or original_state['url'] != current_state['url']

    def _should_return_based_on_state_change(self, original_state, current_state):
        """Determine if the current page state change warrants returning to the original site."""
        # This is a very basic heuristic. In a real application, you'd
        # have a more sophisticated logic for deciding when to return.
        # For example, if the title changes significantly and it's not a common
        # navigation (like a new tab/window), it might indicate a navigation.
        # We'll return True if the title changes and the URL is different.
        return original_state['title'] != current_state['title'] and original_state['url'] != current_state['url']


async def get_clickable_elements(page):
    """Find clickable elements on the page (legacy function for compatibility)"""
    elements = await page.query_selector_all(
        "a[href], button, [role='button'], input[type='submit'], [onclick]"
    )
    valid_elements = []
    for el in elements:
        try:
            href = await el.get_attribute("href")
            if href:
                # Ensure we don't click external links
                if not href.startswith("http") or urlparse(href).netloc == urlparse(BASE_URL).netloc:
                    valid_elements.append(el)
            else:
                valid_elements.append(el)
        except:
            continue
    return valid_elements


async def get_text_inputs(page):
    """Get text input elements (legacy function for compatibility)"""
    return await page.query_selector_all("input[type='text'], input:not([type]), textarea")


async def get_xpath(element):
    """Generate unique XPath for an element"""
    return await element.evaluate("""
        el => {
            function getElementXPath(elt) {
                var path = "";
                for (; elt && elt.nodeType === 1; elt = elt.parentNode) {
                    var idx = 1;
                    for (var sib = elt.previousSibling; sib; sib = sib.previousSibling) {
                        if (sib.nodeType === 1 && sib.tagName === elt.tagName) idx++;
                    }
                    var xname = elt.tagName.toLowerCase();
                    path = "/" + xname + "[" + idx + "]" + path;
                }
                return path;
            }
            return getElementXPath(el);
        }
    """)


async def main():
    """Main execution function"""
    async with async_playwright() as p:
        # Initialize fresh error.json file for this execution
        initialize_error_json()
        
        # Launch browser
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        # No screenshot directory needed - all errors saved to error.json

        # Enhanced error listeners with detailed information
        async def on_page_error(err):
            # Try to extract detailed error information from page errors
            error_details = {}
            
            # Extract error message and stack trace
            if hasattr(err, 'message'):
                error_details['message'] = err.message
            if hasattr(err, 'stack'):
                error_details['stack'] = err.stack
                error_details['stackTrace'] = err.stack
            
            # Try to extract location information from stack trace
            if hasattr(err, 'stack') and err.stack:
                import re
                pattern = r'([^:\s]+):(\d+):(\d+)'
                match = re.search(pattern, str(err.stack))
                if match:
                    error_details['filename'] = match.group(1)
                    error_details['lineno'] = int(match.group(2))
                    error_details['colno'] = int(match.group(3))
            
            # Add navigation context if navigation is in progress
            if navigation_in_progress:
                error_details['navigation_context'] = True
                error_details['navigation_url'] = page.url
                navigation_errors.append({
                    'error': str(err),
                    'details': error_details,
                    'timestamp': datetime.now().isoformat()
                })
            
            # Try to fetch code context if we have filename and line number
            if error_details.get('filename') and error_details.get('lineno') and error_details.get('filename') != 'Unknown':
                try:
                    code_context = await get_code_context_from_location(page, error_details['filename'], error_details['lineno'])
                    if code_context:
                        error_details['code_context'] = code_context
                except Exception as e:
                    print(f"Failed to fetch code context: {e}")
            
            await handle_error(page, f"pageerror_{random.randint(1000,9999)}.png", str(err), "page_error", error_details)
        
        page.on("pageerror", lambda err: asyncio.create_task(on_page_error(err)))

        async def on_console(msg):
            if msg.type == "error":
                # Try to extract detailed error information from console messages
                error_details = {}
                
                # Use Playwright's msg.location() API to get exact file URLs
                loc = msg.location() if callable(getattr(msg, "location", None)) else None
                if loc:
                    error_details['filename'] = loc.get('url', 'Unknown')
                    error_details['lineno'] = loc.get('lineNumber', 'Unknown')
                    error_details['colno'] = loc.get('columnNumber', 'Unknown')
                    print(f"🎯 Console error location: {loc.get('url')}:{loc.get('lineNumber')}:{loc.get('columnNumber')}")
                
                # Fallback: Try to extract error details from the message text if location not available
                if not loc and msg.text:
                    # Look for file:line:column patterns in the message
                    import re
                    pattern = r'([^:\s]+):(\d+):(\d+)'
                    match = re.search(pattern, msg.text)
                    if match and not error_details.get('filename'):
                        error_details['filename'] = match.group(1)
                        error_details['lineno'] = int(match.group(2))
                        error_details['colno'] = int(match.group(3))
                    
                    # Also look for common error patterns that might indicate location
                    # For example: "at filename.js:123:45" or "in filename.js:123"
                    location_patterns = [
                        r'at\s+([^:\s]+):(\d+):(\d+)',
                        r'in\s+([^:\s]+):(\d+)',
                        r'([^:\s]+\.js):(\d+):(\d+)',
                        r'([^:\s]+\.html):(\d+):(\d+)'
                    ]
                    
                    for pattern in location_patterns:
                        match = re.search(pattern, msg.text)
                        if match and not error_details.get('filename'):
                            if len(match.groups()) == 3:
                                error_details['filename'] = match.group(1)
                                error_details['lineno'] = int(match.group(2))
                                error_details['colno'] = int(match.group(3))
                            elif len(match.groups()) == 2:
                                error_details['filename'] = match.group(1)
                                error_details['lineno'] = int(match.group(2))
                            break
                
                # Add navigation context if navigation is in progress
                if navigation_in_progress:
                    error_details['navigation_context'] = True
                    error_details['navigation_url'] = page.url
                    navigation_errors.append({
                        'error': msg.text,
                        'details': error_details,
                        'timestamp': datetime.now().isoformat()
                    })
                
                # Try to fetch code context if we have file URL and line number
                if error_details.get('filename') and error_details.get('lineno') and error_details.get('filename') != 'Unknown':
                    try:
                        code_context = await get_code_context_from_location(page, error_details['filename'], error_details['lineno'])
                        if code_context:
                            error_details['code_context'] = code_context
                    except Exception as e:
                        print(f"Failed to fetch code context: {e}")
                
                await handle_error(page, f"consoleerror_{random.randint(1000,9999)}.png", msg.text, "console_error", error_details)
        
        page.on("console", on_console)

        # Capture unhandled promise rejections with detailed information
        async def on_promise_rejection(event):
            # Try to extract detailed error information from promise rejections
            error_details = {}
            
            # Extract error reason and stack trace
            if hasattr(event, 'reason'):
                reason = event.reason
                if hasattr(reason, 'message'):
                    error_details['message'] = reason.message
                if hasattr(reason, 'stack'):
                    error_details['stack'] = reason.stack
                    error_details['stackTrace'] = reason.stack
                
                # Try to extract location information from stack trace
                if hasattr(reason, 'stack') and reason.stack:
                    import re
                    pattern = r'([^:\s]+):(\d+):(\d+)'
                    match = re.search(pattern, str(reason.stack))
                    if match:
                        error_details['filename'] = match.group(1)
                        error_details['lineno'] = int(match.group(2))
                        error_details['colno'] = int(match.group(3))
            
            # Try to fetch code context if we have filename and line number
            if error_details.get('filename') and error_details.get('lineno') and error_details.get('filename') != 'Unknown':
                try:
                    code_context = await get_code_context_from_location(page, error_details['filename'], error_details['lineno'])
                    if code_context:
                        error_details['code_context'] = code_context
                except Exception as e:
                    print(f"Failed to fetch code context: {e}")
            
            await handle_error(page, f"promise_rejection_{random.randint(1000,9999)}.png", str(event.reason), "promise_rejection", error_details)
        
        page.on("unhandledrejection", lambda event: asyncio.create_task(on_promise_rejection(event)))

        # Enhanced Navigation Guard - Allow navigation but return immediately
        original_url = BASE_URL
        
        async def handle_navigation(new_url, element_info=None):
            """Handle navigation by capturing errors and returning to original page"""
            global navigation_in_progress, navigation_errors, current_element_info
            
            if new_url == original_url:
                return  # Same page, no action needed
            
            # Use current element info if not provided
            if element_info is None:
                element_info = current_element_info
            
            print(f"🔄 Navigation detected: {new_url}")
            if element_info:
                print(f"   Caused by element: {element_info.get('text', 'Unknown')}")
            navigation_in_progress = True
            navigation_errors = []
            
            # Wait for page to load and capture any errors
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=5000)
                await asyncio.sleep(2)  # Wait for any delayed errors
            except:
                pass
            
            # Capture any errors that occurred during navigation
            if navigation_errors:
                print(f"🚨 Captured {len(navigation_errors)} errors during navigation")
                for nav_error in navigation_errors:
                    error_details = nav_error['details']
                    error_details['navigation_url'] = new_url
                    error_details['element_that_caused_navigation'] = element_info.get('text', 'Unknown') if element_info else 'Unknown'
                    
                    await handle_error(
                        page, 
                        f"navigation_error_{random.randint(1000,9999)}.png", 
                        nav_error['error'], 
                        "navigation_error", 
                        error_details
                    )
            
            # Return to original page with robust error handling
            print(f"🏠 Returning to original page: {original_url}")
            return_success = False
            
            # Method 1: Try direct navigation
            try:
                await page.goto(original_url, wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(2)  # Wait longer for page to stabilize
                print(f"✅ Successfully returned to original page")
                return_success = True
            except Exception as e:
                print(f"❌ Method 1 failed: {e}")
            
            # Method 2: Try reload if we're still on the original domain
            if not return_success:
                try:
                    def extract_domain(url):
                        try:
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            return parsed.netloc
                        except:
                            return url
                    
                    current_domain = extract_domain(page.url)
                    target_domain = extract_domain(original_url)
                    if current_domain == target_domain:
                        await page.reload(wait_until="domcontentloaded", timeout=15000)
                        await asyncio.sleep(2)
                        print(f"🔄 Reloaded page as fallback")
                        return_success = True
                except Exception as e:
                    print(f"❌ Method 2 failed: {e}")
            
            # Method 3: Try navigation with longer timeout and different wait strategy
            if not return_success:
                try:
                    await page.goto(original_url, wait_until="load", timeout=20000)
                    await asyncio.sleep(3)
                    print(f"✅ Successfully returned to original page (Method 3)")
                    return_success = True
                except Exception as e:
                    print(f"❌ Method 3 failed: {e}")
            
            # Method 4: Last resort - try to navigate without waiting for load
            if not return_success:
                try:
                    await page.goto(original_url, wait_until="commit", timeout=10000)
                    await asyncio.sleep(5)  # Wait longer for page to load naturally
                    print(f"✅ Successfully returned to original page (Method 4)")
                    return_success = True
                except Exception as e:
                    print(f"❌ Method 4 failed: {e}")
            
            # Method 5: Final fallback - try to navigate with minimal wait
            if not return_success:
                try:
                    print(f"🆘 Trying minimal navigation approach...")
                    # Try navigation with minimal wait and no specific load state
                    await page.goto(original_url, timeout=30000)
                    await asyncio.sleep(5)  # Wait longer for page to load naturally
                    print(f"✅ Successfully returned to original page (Method 5)")
                    return_success = True
                except Exception as e:
                    print(f"❌ Method 5 failed: {e}")
                    print(f"🚨 CRITICAL: Unable to return to original page. Script may need manual intervention.")
            
            if not return_success:
                print(f"⚠️ WARNING: Failed to return to original page after all attempts")
            
            navigation_in_progress = False

        # Monitor page navigation
        page.on("framenavigated", lambda frame: asyncio.create_task(handle_navigation(frame.url)))
        
        def set_current_element_info(element_info):
            """Set current element info for navigation context"""
            global current_element_info
            current_element_info = element_info

        # Listen for custom error events with detailed information
        async def on_custom_error(event_data):
            try:
                # Parse the event data to extract detailed error information
                error_details = {}
                
                if isinstance(event_data, dict):
                    error_details = event_data
                elif isinstance(event_data, str):
                    # Try to parse JSON string
                    try:
                        import json
                        error_details = json.loads(event_data)
                    except:
                        error_details = {'message': event_data}
                
                # Extract error message
                error_message = error_details.get('message', error_details.get('reason', str(event_data)))
                
                # Try to fetch code context if we have filename and line number
                if error_details.get('filename') and error_details.get('lineno') and error_details.get('filename') != 'Unknown':
                    try:
                        code_context = await get_code_context_from_location(page, error_details['filename'], error_details['lineno'])
                        if code_context:
                            error_details['code_context'] = code_context
                    except Exception as e:
                        print(f"Failed to fetch code context: {e}")
                
                await handle_error(
                    page, 
                    # screenshot_dir, # This line was removed as per the new_code, as it's not defined.
                    f"custom_error_{random.randint(1000,9999)}.png", 
                    error_message, 
                    error_details.get('type', 'custom_error'),
                    error_details
                )
            except Exception as e:
                print(f"Failed to handle custom error: {e}")
        
        await page.expose_function("logError", lambda detail: asyncio.create_task(on_custom_error(detail)))

        # Inject enhanced error monitoring script
        await page.add_init_script("""
            // Enhanced error monitoring with detailed information capture
            const originalConsoleError = console.error;
            const originalConsoleWarn = console.warn;
            const originalConsoleLog = console.log;
            
            // Track click events to correlate with errors
            let clickEventCount = 0;
            let lastClickTime = null;
            
            // Monitor all click events
            document.addEventListener('click', function(event) {
                clickEventCount++;
                lastClickTime = new Date().toISOString();
                
                // Log click event for debugging
                console.log(`[DEBUG] Click event ${clickEventCount} on ${event.target.tagName} at ${lastClickTime}`);
            }, true);
            
            // Function to capture detailed error information
            function captureErrorDetails(error, type = 'console.error', context = {}) {
                const errorInfo = {
                    type: type,
                    message: error?.message || error?.toString() || 'Unknown error',
                    stack: error?.stack || new Error().stack,
                    stackTrace: error?.stack || new Error().stack,
                    timestamp: new Date().toISOString(),
                    url: window.location.href,
                    clickEventCount: clickEventCount,
                    lastClickTime: lastClickTime,
                    ...context
                };
                
                // Try to extract line and column information from stack trace
                if (error?.stack) {
                    const stackLines = error.stack.split('\\n');
                    for (let line of stackLines) {
                        if (line.includes(':')) {
                            const match = line.match(/([^\\s]+):(\\d+):(\\d+)/);
                            if (match) {
                                errorInfo.filename = match[1];
                                errorInfo.lineno = parseInt(match[2]);
                                errorInfo.colno = parseInt(match[3]);
                                break;
                            }
                        }
                    }
                }
                
                // Dispatch custom event with detailed error info
                window.dispatchEvent(new CustomEvent('jsError', { 
                    detail: errorInfo 
                }));
                
                return errorInfo;
            }
            
            // Override console.error to capture detailed information
            console.error = function(...args) {
                let errorObj = null;
                let context = {};
                
                // Try to find an Error object in the arguments
                for (let arg of args) {
                    if (arg instanceof Error) {
                        errorObj = arg;
                        break;
                    }
                }
                
                // If no Error object found, create one from the message
                if (!errorObj) {
                    errorObj = new Error(args.join(' '));
                    // Try to capture call stack
                    errorObj.stack = new Error().stack;
                }
                
                // Add click context if this error occurred after a click
                if (lastClickTime) {
                    context.clickContext = {
                        clickEventCount: clickEventCount,
                        lastClickTime: lastClickTime,
                        timeSinceClick: Date.now() - new Date(lastClickTime).getTime()
                    };
                }
                
                const errorInfo = captureErrorDetails(errorObj, 'console.error', context);
                
                // Call original console.error
                return originalConsoleError.apply(console, args);
            };
            
            // Override console.warn to capture warnings
            console.warn = function(...args) {
                const errorInfo = captureErrorDetails(new Error(args.join(' ')), 'console.warn');
                return originalConsoleWarn.apply(console, args);
            };
            
            // Monitor for unhandled errors with detailed information
            window.addEventListener('error', function(event) {
                const errorInfo = {
                    type: 'unhandled_error',
                    message: event.message,
                    filename: event.filename,
                    lineno: event.lineno,
                    colno: event.colno,
                    error: event.error ? event.error.stack : 'No stack trace',
                    stack: event.error ? event.error.stack : 'No stack trace',
                    stackTrace: event.error ? event.error.stack : 'No stack trace',
                    timestamp: new Date().toISOString(),
                    url: window.location.href,
                    clickEventCount: clickEventCount,
                    lastClickTime: lastClickTime
                };
                
                window.dispatchEvent(new CustomEvent('jsError', { 
                    detail: errorInfo 
                }));
            });
            
            // Monitor for unhandled promise rejections with detailed information
            window.addEventListener('unhandledrejection', function(event) {
                let errorInfo = {
                    type: 'unhandled_promise_rejection',
                    reason: event.reason,
                    timestamp: new Date().toISOString(),
                    url: window.location.href,
                    clickEventCount: clickEventCount,
                    lastClickTime: lastClickTime
                };
                
                // Try to extract detailed information from the rejection reason
                if (event.reason instanceof Error) {
                    errorInfo.message = event.reason.message;
                    errorInfo.stack = event.reason.stack;
                    errorInfo.stackTrace = event.reason.stack;
                    
                    // Extract line and column from stack trace
                    if (event.reason.stack) {
                        const stackLines = event.reason.stack.split('\\n');
                        for (let line of stackLines) {
                            if (line.includes(':')) {
                                const match = line.match(/([^\\s]+):(\\d+):(\\d+)/);
                                if (match) {
                                    errorInfo.filename = match[1];
                                    errorInfo.lineno = parseInt(match[2]);
                                    errorInfo.colno = parseInt(match[3]);
                                    break;
                                }
                            }
                        }
                    }
                } else if (typeof event.reason === 'string') {
                    errorInfo.message = event.reason;
                }
                
                window.dispatchEvent(new CustomEvent('jsError', { 
                    detail: errorInfo 
                }));
            });
            
            // Monitor for resource loading errors
            window.addEventListener('error', function(event) {
                if (event.target !== window) {
                    const errorInfo = {
                        type: 'resource_error',
                        message: `Failed to load resource: ${event.target.src || event.target.href}`,
                        filename: event.target.src || event.target.href,
                        timestamp: new Date().toISOString(),
                        url: window.location.href,
                        clickEventCount: clickEventCount,
                        lastClickTime: lastClickTime
                    };
                    
                    window.dispatchEvent(new CustomEvent('jsError', { 
                        detail: errorInfo 
                    }));
                }
            }, true);
            
            // Monitor for fetch errors
            const originalFetch = window.fetch;
            window.fetch = function(...args) {
                return originalFetch.apply(this, args).catch(error => {
                    const errorInfo = {
                        type: 'fetch_error',
                        message: error.message,
                        stack: error.stack,
                        stackTrace: error.stack,
                        timestamp: new Date().toISOString(),
                        url: window.location.href,
                        fetchUrl: args[0],
                        clickEventCount: clickEventCount,
                        lastClickTime: lastClickTime
                    };
                    
                    window.dispatchEvent(new CustomEvent('jsError', { 
                        detail: errorInfo 
                    }));
                    
                    throw error;
                });
            };
            
            // Monitor for XMLHttpRequest errors
            const originalXHROpen = XMLHttpRequest.prototype.open;
            const originalXHRSend = XMLHttpRequest.prototype.send;
            
            XMLHttpRequest.prototype.open = function(method, url, ...args) {
                this._errorUrl = url;
                return originalXHROpen.apply(this, [method, url, ...args]);
            };
            
            XMLHttpRequest.prototype.send = function(...args) {
                this.addEventListener('error', function() {
                    const errorInfo = {
                        type: 'xhr_error',
                        message: 'XMLHttpRequest failed',
                        timestamp: new Date().toISOString(),
                        url: window.location.href,
                        xhrUrl: this._errorUrl,
                        clickEventCount: clickEventCount,
                        lastClickTime: lastClickTime
                    };
                    
                    window.dispatchEvent(new CustomEvent('jsError', { 
                        detail: errorInfo 
                    }));
                });
                
                return originalXHRSend.apply(this, args);
            };
            
            // Monitor for navigation errors
            window.addEventListener('beforeunload', function(event) {
                const errorInfo = {
                    type: 'navigation_error',
                    message: 'Page navigation/refresh detected',
                    timestamp: new Date().toISOString(),
                    url: window.location.href,
                    clickEventCount: clickEventCount,
                    lastClickTime: lastClickTime
                };
                
                window.dispatchEvent(new CustomEvent('jsError', { 
                    detail: errorInfo 
                }));
            });
        """)

        # Set up listener for custom error events
        await page.evaluate("""
            window.addEventListener('jsError', function(event) {
                window.logError(event.detail);
            });
        """)

        print(f"🌐 Navigating to: {BASE_URL}")
        await page.goto(BASE_URL, wait_until="domcontentloaded")
        await asyncio.sleep(3)  # Wait for page to fully load

        # Initialize advanced blind interaction strategy
        blind_strategy = AdvancedBlindInteractionStrategy(page)
        
        print("🚀 Starting advanced recursive error capture session...")
        
        # Phase 1: Click all links and buttons to capture console errors
        print("🔍 Phase 1: Clicking all links and buttons to capture console errors...")
        clicking_summary = await blind_strategy.click_all_links_and_buttons()
        
        # Wait a bit to capture any delayed console errors
        print("⏳ Waiting for console errors to be captured...")
        await asyncio.sleep(3)
        
        # Display clicking summary
        print(f"\n📊 Phase 1 Summary:")
        print(f"   Total clickable elements found: {clicking_summary['total_elements_found']}")
        print(f"   Successfully clicked: {clicking_summary['successfully_clicked']}")
        print(f"   Console errors captured: {len(seen_errors)}")
        
        # Phase 2: Test input fields and dropdowns
        print("\n🔍 Phase 2: Testing input fields and dropdowns...")
        await blind_strategy.test_input_fields_specifically()
        
        # Phase 3: Recursive exploration with XPath tracking (if needed)
        print("🔍 Phase 3: Recursive exploration with XPath tracking...")
        await blind_strategy.recursive_monkey_exploration()
        
        # Phase 4: Stress testing (if we haven't reached max actions)
        if blind_strategy.actions_performed < MAX_ACTIONS:
            await blind_strategy.stress_test_interactions(duration_seconds=15)
        
        # Final wait to catch any delayed errors
        print("⏳ Final wait for delayed errors...")
        await asyncio.sleep(5)
        
        print(f"\n📊 Advanced Recursive Error Capture Session Complete!")
        print(f"Total actions performed: {blind_strategy.actions_performed}")
        print(f"Unique elements visited: {len(visited_selectors)}")
        print(f"Unique errors captured: {len(seen_errors)}")
        print(f"All errors saved to: {error_json_file}")
        
        # Display final summary
        await display_final_summary()

        await browser.close()


async def display_final_summary():
    """Display final summary of captured errors from single JSON file"""
    try:
        import json
        
        # Read the single error JSON file
        try:
            with open(error_json_file, 'r', encoding='utf-8') as f:
                error_data = json.load(f)
            
            total_errors = len(error_data.get("errors", []))
            
            if total_errors == 0:
                print("✅ No errors were captured during this session.")
                return
            
            print(f"\n📈 Final Error Capture Summary:")
            print(f"📋 Total errors captured: {total_errors}")
            print(f"💾 All errors saved to: {error_json_file}")
            print(f"🔍 Error deduplication prevented duplicate reporting")
            
            # Show error types summary
            error_types = {}
            for error in error_data.get("errors", []):
                error_type = error.get("error_type", "unknown")
                error_types[error_type] = error_types.get(error_type, 0) + 1
            
            print(f"📊 Error types captured:")
            for error_type, count in error_types.items():
                print(f"   - {error_type}: {count}")
            
        except FileNotFoundError:
            print("✅ No errors were captured during this session.")
        except Exception as e:
            print(f"❌ Failed to read error summary: {e}")
            
    except Exception as e:
        print(f"❌ Failed to display final summary: {e}")


if __name__ == "__main__":
    asyncio.run(main()) 

