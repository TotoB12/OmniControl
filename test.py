import google.generativeai as genai
import os
from dotenv import load_dotenv
import typing_extensions
import PIL.Image
load_dotenv()

genai.configure(api_key=os.environ["API_KEY"])

class Action(typing_extensions.TypedDict):
	reasoning: str
	action_type: str
	action_element_id: str
	value: str

model = genai.GenerativeModel(
	"gemini-1.5-flash",
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
        response_schema = list[Action]),
    system_instruction="You are a helpfull assistant.",
	)

chat = model.start_chat()

image = PIL.Image.open("screenshot.png")

response = chat.send_message(["What is this?", image])
print(response.text)