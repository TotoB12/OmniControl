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

# Window configuration
Window.size = (1024, 768)
Window.top = 100
Window.left = 100
Window.borderless = False

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
        
        # Create UI elements
        self._create_input_section()
        self._create_content_section()
        self._create_status_bar()
        
        # Initialize processing state
        self.processing = False

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
        
        # Right side - Parser Results
        right_panel = BoxLayout(orientation='vertical', size_hint_x=0.5)
        right_panel.add_widget(Label(
            text='Parser Results',
            size_hint_y=None,
            height=30,
            bold=True
        ))
        
        self.results_view = ScrollableLabel(size_hint=(1, 1))
        right_panel.add_widget(self.results_view)
        
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

    def take_screenshot(self, *args):
        if self.processing:
            return
            
        self.processing = True
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
            
            # Update screenshot display immediately
            Clock.schedule_once(lambda dt: self._update_screenshot(self.screenshot_path))
            
            # Process with OmniParser in a separate thread
            Thread(target=self._process_with_omniparser).start()
            
        except Exception as e:
            self.status_label.text = f"Error taking screenshot: {str(e)}"
            self.processing = False

    def _update_screenshot(self, path):
        self.screenshot_image.source = path
        self.screenshot_image.reload()

    def _process_with_omniparser(self):
        try:
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
            post_url = 'http://127.0.0.1:7860/gradio_api/call/process'
            post_response = requests.post(post_url, json=payload)
            
            if post_response.status_code != 200:
                raise Exception(f"POST request failed with status code {post_response.status_code}")
            
            # Get event_id
            event_id = post_response.json().get('event_id')
            print(f"Event ID: {event_id}")
            
            if not event_id:
                raise Exception("No event_id returned from POST request")
            
            # Poll for the result
            get_url = f'http://127.0.0.1:7860/gradio_api/call/process/{event_id}'
            get_response = requests.get(get_url, stream=True)
            
            if get_response.status_code != 200:
                raise Exception(f"GET request failed with status code {get_response.status_code}")
            
            # Read the stream
            result_data = None
            event = None
            for line in get_response.iter_lines(decode_unicode=True):
                if line:
                    if line.startswith('event:'):
                        event = line[len('event:'):].strip()
                        # print(f"Event: {event}")
                    elif line.startswith('data:'):
                        data_line = line[len('data:'):].strip()
                        # data_line is JSON string
                        result_data = json.loads(data_line)
                        # print(f"Data: {result_data}")
                        if event == 'complete':
                            break
            
            if result_data is None:
                raise Exception("No data received from GET request")

            url = f"http://127.0.0.1:7860/gradio_api/file={result_data[0].get('path')}"
            text = result_data[1]
            coordinates = ast.literal_eval(result_data[2])

            output = {
                "url": url,
                "text": text,
                "coordinates": coordinates
            }
            print(f"Output: {output}")
            
            # Update UI in the main thread
            Clock.schedule_once(lambda dt: self._handle_parser_result(output))
            
        except Exception as e:
            error_message = str(e)
            Clock.schedule_once(lambda dt: self._handle_parser_error(error_message))

    def _handle_parser_result(self, result_data):
        parsed_image_url = result_data["url"]
        parsed_text = result_data["text"] + "\n\n" + str(result_data["coordinates"])
        
        # Update the results text
        self.results_view.update_text(self._format_parser_results(parsed_text))
        
        # Update the image if a URL was returned
        if parsed_image_url:
            self.screenshot_image.source = parsed_image_url
            self.screenshot_image.reload()
        
        self.status_label.text = "Processing complete"
        self.processing = False

    def _handle_parser_error(self, error_message):
        self.status_label.text = f"Error: {error_message}"
        self.results_view.update_text(f"Error processing screenshot:\n{error_message}")
        self.processing = False

    def _format_parser_results(self, parser_output):
        formatted_text = "[b]Detected Elements:[/b]\n\n"
        elements = parser_output.split('\n')
        return formatted_text + "\n".join(f"• {element}" for element in elements if element.strip())

    def start_job(self, instance):
        prompt = self.user_input.text
        if prompt.strip() == '':
            self.status_label.text = "Please enter a prompt."
        elif not self.processing:
            self.status_label.text = f"Starting job: {prompt}"
            Clock.schedule_once(self.take_screenshot, 0.1)

class MyKivyApp(App):
    def build(self):
        return MyAppLayout()

if __name__ == '__main__':
    MyKivyApp().run()
