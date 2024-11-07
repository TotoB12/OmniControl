import kivy
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.uix.image import Image
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import ObjectProperty
import pyautogui
import os
import tempfile
from datetime import datetime
import base64
from threading import Thread
import requests
import json
import ast
from dotenv import load_dotenv
import google.generativeai as genai
import PIL.Image
import typing_extensions
from datetime import datetime
from urllib.parse import quote

# Load environment variables
load_dotenv()
genai.configure(api_key=os.environ["API_KEY"])

# Window configuration
Window.size = (1024, 768)
Window.top = 100
Window.left = 100
Window.borderless = False

parser_address = "http://127.0.0.1:7860"

# class Action(typing_extensions.TypedDict):
#     reasoning: str
#     action_type: str
#     action_element_id: str
#     value: str

class EventLog:
    def __init__(self):
        self.events = []
    
    def add_event(self, event_type: str, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.events.append(f"[{timestamp}] [{event_type}] {message}")
    
    def get_formatted_log(self):
        return "\n".join(self.events)

class ScrollableLabel(ScrollView):
    text = ObjectProperty('')

    def __init__(self, **kwargs):
        super(ScrollableLabel, self).__init__(**kwargs)
        self.label = Label(
            text=self.text,
            markup=True,
            size_hint_y=None,
            padding=(10, 10)
        )
        self.label.bind(texture_size=self._set_label_height)
        self.add_widget(self.label)

    def _set_label_height(self, instance, size):
        instance.height = size[1]
        instance.text_size = (instance.width, None)

    def update_text(self, new_text):
        self.label.text = new_text

class MyAppLayout(BoxLayout):
    def __init__(self, **kwargs):
        super(MyAppLayout, self).__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(10)
        self.spacing = dp(10)
        
        # Initialize event log
        self.event_log = EventLog()
        
        # Initialize AI model
        self.model = genai.GenerativeModel(
            "gemini-1.5-flash",
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
            ),
            system_instruction=(
                """
                You are an AI assistant designed to completed the user's objective by providing executing actions step-by-step on the user's machine. You will be provided with an annotated screenshot of the user's screen, and will have to determine the best next action to take in order to achieve the goal. You can interact with the screen by clicking, typing, and scrolling. You should always follow this format when providing an action:

                [
                    {
                        "reasoning": "Explain why you are taking this action; required.",
                        "action_type": "The type of action to take (click, type, scroll); required.",
                        "action_element_id": "The numeral ID of the element to interact with; required.",
                        "value": "The value to type in the element; optional."
                    }
                ]

                You should only do one action at a time. Only respond with the next action to take.
                Here are some examples of actions you can take:

                [
                    {
                        "reasoning": "Click the 'Submit' button to submit the form.",
                        "action_type": "click",
                        "action_element_id": "45"
                    }
                ]

                [
                    {
                        "reasoning": "Type 'hello' in the text box.",
                        "action_type": "type",
                        "action_element_id": "12",
                        "value": "hello"
                    }
                ]

                [
                    {
                        "reasoning": "Scroll down to view more content.",
                        "action_type": "scroll",
                        "action_element_id": "103"
                    }
                ]
                """
            )
        )
        self.chat = self.model.start_chat()
        
        # Create UI elements
        self._create_input_section()
        self._create_content_section()
        self._create_status_bar()
        
        # Initialize processing state
        self.processing = False
        
        self.event_log.add_event("INIT", "Application started")
        self._update_event_log()

    def _create_input_section(self):
        input_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)
        
        self.user_input = TextInput(
            hint_text='Enter your prompt here...',
            multiline=False,
            size_hint_x=0.8
        )
        
        start_button = Button(
            text='Start Job',
            size_hint_x=0.2,
            background_color=(0.2, 0.6, 0.2, 1)
        )
        start_button.bind(on_press=self.start_job)
        
        input_layout.add_widget(self.user_input)
        input_layout.add_widget(start_button)
        self.add_widget(input_layout)

    def _create_content_section(self):
        content_layout = BoxLayout(spacing=10)
        
        # Left side - Screenshot
        left_panel = BoxLayout(orientation='vertical', size_hint_x=0.5)
        left_panel.add_widget(Label(
            text='Screenshot',
            size_hint_y=None,
            height=30,
            bold=True
        ))
        self.screenshot_image = Image(allow_stretch=True)
        left_panel.add_widget(self.screenshot_image)
        
        # Right side - Event Log
        right_panel = BoxLayout(orientation='vertical', size_hint_x=0.5)
        right_panel.add_widget(Label(
            text='Event Log',
            size_hint_y=None,
            height=30,
            bold=True
        ))
        
        self.event_view = ScrollableLabel(size_hint=(1, 1))
        right_panel.add_widget(self.event_view)
        
        content_layout.add_widget(left_panel)
        content_layout.add_widget(right_panel)
        self.add_widget(content_layout)

    def _create_status_bar(self):
        self.status_label = Label(
            text='Ready',
            size_hint_y=None,
            height=30,
            halign='left'
        )
        self.add_widget(self.status_label)

    def _update_event_log(self):
        self.event_view.update_text(self.event_log.get_formatted_log())

    def take_screenshot(self, *args):
        if self.processing:
            return
            
        self.processing = True
        self.event_log.add_event("SCREEN", "Taking screenshot...")
        self._update_event_log()
        self.status_label.text = "Taking screenshot..."
        Window.minimize()
        Clock.schedule_once(self._capture_and_process, 0.2)

    def _capture_and_process(self, *args):
        try:
            # Take and save screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_dir = tempfile.gettempdir()
            self.screenshot_path = os.path.join(temp_dir, f'screenshot_{timestamp}.png')
            
            screenshot = pyautogui.screenshot()
            screenshot.save(self.screenshot_path)
            Window.restore()
            
            self.event_log.add_event("SCREEN", f"Screenshot saved: {self.screenshot_path}")
            self._update_event_log()
            
            # Update screenshot display immediately
            Clock.schedule_once(lambda dt: self._update_screenshot(self.screenshot_path))
            
            # Process with OmniParser in a separate thread
            Thread(target=self._process_with_omniparser).start()
            
        except Exception as e:
            error_msg = f"Error taking screenshot: {str(e)}"
            self.event_log.add_event("ERROR", error_msg)
            self._update_event_log()
            self.status_label.text = error_msg
            self.processing = False

    def _update_screenshot(self, path):
        self.screenshot_image.source = path
        self.screenshot_image.reload()

    def _process_with_omniparser(self):
        try:
            self.event_log.add_event("PARSER", "Processing with OmniParser...")
            self._update_event_log()
            self.status_label.text = "Processing with OmniParser..."
            
            # Convert image to base64
            with open(self.screenshot_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Prepare payload
            payload = {
                "data": [
                    {
                        "url": f"data:image/png;base64,{encoded_string}",
                        "size": os.path.getsize(self.screenshot_path),
                        "orig_name": os.path.basename(self.screenshot_path),
                        "mime_type": "image/png"
                    },
                    0.05,  # box_threshold
                    0.1    # iou_threshold
                ]
            }
            
            # Send POST request
            post_url = parser_address + '/gradio_api/call/process'
            post_response = requests.post(post_url, json=payload)
            
            if post_response.status_code != 200:
                raise Exception(f"POST request failed with status code {post_response.status_code}")
            
            # Get event_id
            event_id = post_response.json().get('event_id')
            self.event_log.add_event("PARSER", f"Processing event ID: {event_id}")
            self._update_event_log()
            
            if not event_id:
                raise Exception("No event_id returned from POST request")
            
            # Poll for the result
            get_url = parser_address + f'/gradio_api/call/process/{event_id}'
            get_response = requests.get(get_url, stream=True)
            
            if get_response.status_code != 200:
                raise Exception(f"GET request failed with status code {get_response.status_code}")
            
            # Read the stream
            result_data = None
            for line in get_response.iter_lines(decode_unicode=True):
                if line and line.startswith('data:'):
                    data_line = line[len('data:'):].strip()
                    result_data = json.loads(data_line)
                    if result_data:
                        break
            
            if result_data is None:
                raise Exception("No data received from GET request")

            parsed_output = {
                "url": parser_address + f"/gradio_api/file={result_data[0].get('path')}",
                "text": result_data[1],
                "coordinates": ast.literal_eval(result_data[2])
            }
            
            self.event_log.add_event("PARSER", "OmniParser processing complete")
            self.event_log.add_event("PARSER", f"Text output: {parsed_output['text']}")
            self._update_event_log()

            self.screenshot_image.source = parsed_output["url"]
            self.screenshot_image.reload()
            
            # Process with AI in a separate thread
            Thread(target=self._process_with_ai, args=(parsed_output,)).start()
            
        except Exception as e:
            error_message = str(e)
            Clock.schedule_once(lambda dt: self._handle_parser_error(error_message))

    def _process_with_ai(self, parser_output):
        try:
            self.event_log.add_event("AI", "Starting AI analysis...")
            self._update_event_log()
            
            # Load the annotated image
            image = PIL.Image.open(self.screenshot_path)
            
            # Prepare the prompt with the user's objective and parser output
            prompt = [
                f"User objective:\n\n```{self.user_input.text}\n```\n\n"
                f"Screen elements detected:\n\n```{parser_output['text']}\n```",
                image
            ]
            
            # Send to AI
            response = self.chat.send_message(prompt)
            
            Clock.schedule_once(lambda dt: self._handle_ai_response(response.text))
            
        except Exception as e:
            error_message = str(e)
            Clock.schedule_once(lambda dt: self._handle_ai_error(error_message))

    def _handle_parser_result(self, result_data):
        self.event_log.add_event("PARSER", "Parser processing complete")
        self._update_event_log()
        
        if result_data.get("url"):
            self.screenshot_image.source = result_data["url"]
            self.screenshot_image.reload()
        
        self.status_label.text = "Processing complete"

    def _handle_parser_error(self, error_message):
        self.event_log.add_event("ERROR", f"Parser error: {error_message}")
        self._update_event_log()
        self.status_label.text = f"Error: {error_message}"
        self.processing = False

    def _handle_ai_response(self, response_text):
        self.event_log.add_event("AI", f"AI Response received:\n{response_text}")
        self._update_event_log()
        self.status_label.text = "AI processing complete"
        self.processing = False

    def _handle_ai_error(self, error_message):
        self.event_log.add_event("ERROR", f"AI error: {error_message}")
        self._update_event_log()
        self.status_label.text = f"AI Error: {error_message}"
        self.processing = False

    def start_job(self, instance):
        prompt = self.user_input.text
        if prompt.strip() == '':
            self.status_label.text = "Please enter a prompt."
            self.event_log.add_event("ERROR", "Empty prompt")
            self._update_event_log()
        elif not self.processing:
            self.event_log.add_event("JOB", f"Starting new job with prompt: {prompt}")
            self._update_event_log()
            self.status_label.text = f"Starting job: {prompt}"
            Clock.schedule_once(self.take_screenshot, 0.1)

class MyKivyApp(App):
    def build(self):
        return MyAppLayout()

if __name__ == '__main__':
    MyKivyApp().run()