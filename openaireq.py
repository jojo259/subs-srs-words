import requests
import json
import os
import dotenv
dotenv.load_dotenv()

def doRequest(messagesList):

	for message in messagesList:
		if sorted(message.keys()) != sorted(['role', 'content']):
			raise KeyError(f'Wrong keys in messagesList: {message.keys()}')
		for value in message.values():
			if not type(value) == str:
				raise TypeError(f'Wrong type in messagesList values: {type(value)}')

	reqHeaders = {
		'Content-type': 'application/json',
		'Authorization': f'Bearer {os.environ["openaikey"]}',
	}

	reqBody = {
		'model': os.environ['gptmodel'],
		'messages': messagesList,
		'temperature': 0.1,
		'max_tokens': 1000,
		'frequency_penalty': 1,
		'presence_penalty': 0.1,
	}

	apiReq = requests.post('https://api.openai.com/v1/chat/completions', headers = reqHeaders, json = reqBody, timeout = 1000)

	try:
		reponseStr = apiReq.json()['choices'][0]['message']['content']
	except Exception as e: # todo
		return

	return reponseStr

def constructMessage(role, content):
	return {'role': role, 'content': content}
