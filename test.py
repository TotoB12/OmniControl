from gradio_client import Client, handle_file

client = Client("jadechoghari/OmniParser")
result = client.predict(
		image_input=handle_file('C:/Users/totob/OneDrive/PC/Documents/OmniControl/screenshot.png'),
		box_threshold=0.05,
		iou_threshold=0.1,
		api_name="/process"
)
print(result)