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
from gradio_client import Client, handle_file
import base64

# Set the window size (width x height)
Window.size = (1024, 768)  # Increased size to better show results
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
        
        # Initialize OmniParser client
        self.omniparser_client = Client("jadechoghari/OmniParser")
        
        # Create top section for input
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
        
        # Create content area with screenshots and results
        content_layout = BoxLayout(spacing=10)
        
        # Left side - Screenshot
        left_panel = BoxLayout(orientation='vertical', size_hint_x=0.5)
        left_panel.add_widget(Label(
            text='Screenshot',
            size_hint_y=None,
            height=30,
            bold=True
        ))
        self.screenshot_image = Image()
        left_panel.add_widget(self.screenshot_image)
        
        # Right side - Parser Results
        right_panel = BoxLayout(orientation='vertical', size_hint_x=0.5)
        right_panel.add_widget(Label(
            text='Parser Results',
            size_hint_y=None,
            height=30,
            bold=True
        ))
        
        self.results_view = ScrollableLabel(
            size_hint=(1, 1)
        )
        right_panel.add_widget(self.results_view)
        
        content_layout.add_widget(left_panel)
        content_layout.add_widget(right_panel)
        self.add_widget(content_layout)
        
        # Status bar
        self.status_label = Label(
            text='Ready',
            size_hint_y=None,
            height=30,
            halign='left'
        )
        self.add_widget(self.status_label)

    def take_screenshot(self, *args):
        self.status_label.text = "Taking screenshot..."
        Window.minimize()
        Clock.schedule_once(self._capture_and_process, 0.2)

    def _capture_and_process(self, *args):
        # Take and save screenshot
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_dir = tempfile.gettempdir()
        screenshot_path = os.path.join(temp_dir, f'screenshot_{timestamp}.png')
        
        screenshot = pyautogui.screenshot()
        screenshot.save(screenshot_path)
        Window.restore()
        
        # Update screenshot display
        self.screenshot_image.source = screenshot_path
        self.screenshot_image.reload()
        
        # Process with OmniParser
        self.status_label.text = "Processing with OmniParser..."
        try:
            # Convert image to base64 for processing
            with open(screenshot_path, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Process with OmniParser
            result = self.omniparser_client.predict(
                image_input={
                    "url": f"data:image/png;base64,{encoded_string}",
                    "size": os.path.getsize(screenshot_path),
                    "orig_name": os.path.basename(screenshot_path),
                    "mime_type": "image/png"
                },
                box_threshold=0.05,
                iou_threshold=0.1,
                api_name="/process"
            )
            
            # Format and display results
            parsed_text = result[1]
            parsed_image = result[0]
            formatted_results = self._format_parser_results(parsed_text)
            self.results_view.update_text(parsed_text)
            self.status_label.text = "Processing complete"
            
        except Exception as e:
            self.status_label.text = f"Error: {str(e)}"
            self.results_view.update_text(f"Error processing screenshot:\n{str(e)}")

    def _format_parser_results(self, parser_output):
        """Format the parser output for better readability"""
        formatted_text = "[b]Detected Elements:[/b]\n\n"
        
        # Split the output into lines and format each element
        elements = parser_output.split('\n')
        for element in elements:
            if element.strip():
                formatted_text += f"• {element}\n"
        
        return formatted_text

    def start_job(self, instance):
        prompt = self.user_input.text
        if prompt.strip() == '':
            self.status_label.text = "Please enter a prompt."
        else:
            self.status_label.text = f"Starting job: {prompt}"
            Clock.schedule_once(self.take_screenshot, 0.1)

class MyKivyApp(App):
    def build(self):
        return MyAppLayout()

if __name__ == '__main__':
    MyKivyApp().run()