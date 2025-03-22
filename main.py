import os
import subprocess
import jieba
from datetime import datetime
import re
import pinyin
from chin_dict.chindict import ChinDict
import openaireq
import json5
import cchardet

import dotenv
dotenv.load_dotenv()

def chunk(lst, n):
	for i in range(0, len(lst), n):
		yield lst[i:i + n]

def filterNonChinese(texts):
	return [text for text in texts if not re.fullmatch(r'[^\w\u4e00-\u9fff]+', text)]

def extractFrame(time, filename):
	command = [
		'ffmpeg',
		'-ss', time,
		'-i', os.environ['video_path'],
		'-compression_level', '100',
		'-vf', f"\"subtitles='{os.environ['subs_path']}':force_style='FontSize=40,FontName=Noto Sans SC',scale=768:432\"",
		'-frames:v', '1',
		'-qscale:v', '0',
		filename,
		'-y',
		'-copyts',
	]

	command = ' '.join(command) + ' > nul 2>&1'
	subprocess.call(command, shell=True)

def csvProcessText(text):
	return text.replace('|', '/')

def splitUnknownWords(words):
	processedwords = []
	for word in words:
		try:
			wordmeaning = chindict._lookup_word(word).meaning
			processedwords.append(word)
		except:
			processedwords.extend(list(word))
			print(f'split unknown word ' + word + ' into ' + ' and '.join(list(word)))
	return processedwords

ignoreknownwords = True

if os.environ['definewith'] == 'chindict':
	chindict = ChinDict()

if not os.path.exists('images'):
	os.makedirs('images')

with open('words.csv', 'w', encoding="UTF-8") as csvfile:
	csvfile.write('')

knownwords = []
with open('knownwords.txt', mode='r', encoding='UTF-8') as knowns:
	knownwords = knowns.read().splitlines()

donewords = []
failedwords = []
alrknownwords = []
alrdonewords = []

subs_file_encoding = None

print('checking subs file encoding')

with open(os.environ['subs_path'], 'rb') as f:
	raw = f.read(1000000)
	detected = cchardet.detect(raw)
	subs_file_encoding = detected['encoding']
	print(f'subs file encoding: {subs_file_encoding}')

if not subs_file_encoding:
	raise Exception('no subs file encoding')

with open(os.environ['subs_path'], mode='r', encoding=subs_file_encoding) as subs:
	subsall = subs.read()
	subs = list(chunk(subsall.split('\n'), 4))
	for atsub, sub in enumerate(subs[:-1]):
		timesplit = sub[1].split(' --> ')
		readtimeformat = '%H:%M:%S,%f'
		timestart = datetime.strptime(timesplit[0], readtimeformat)
		timeend = datetime.strptime(timesplit[1], readtimeformat)
		timediff = timeend - timestart
		print(f'LINE {sub[2]} at time {timestart}')
		if os.environ['splitwith'] == 'jieba':
			words = filterNonChinese(list(jieba.cut(sub[2])))
			words = splitUnknownWords(words)
		elif os.environ['splitwith'] == 'ai':
			tries = -1
			while True:
				tries += 1
				if tries >= 8:
					print('FAILED ai splitting')
					words = filterNonChinese(list(jieba.cut(sub[2])))
					break
				with open('promptsplit.txt', 'r') as promptFile:
					messages = [
						openaireq.constructMessage('system', promptFile.read()),
						openaireq.constructMessage('user', sub[2])
					]
					resp = None
					while resp == None:
						print('getting ai split')
						resp = openaireq.doRequest(messages)
					print(f'try {tries} response: {resp}')
					try:
						words = filterNonChinese(json5.loads(resp)['items'])
						break
					except Exception as e:
						print(e)
						continue
					print(words)
		for atword, word in enumerate(words):
			if word in knownwords and ignoreknownwords:
				alrknownwords.append(word)
				continue
			if word in donewords or word in failedwords:
				alrdonewords.append(word)
				continue
			ffmpegtimeformat = '%H:%M:%S.%f'
			wordtimeguess = timestart + ((atword + 1) / (len(words) + 1)) * timediff
			wordtimeguessffmpeg = datetime.strftime(wordtimeguess, ffmpegtimeformat)
			wordtimeguesspriolevel = datetime.strftime(wordtimeguess, '%H %M %S %f')
			filetimeformat = '%Hh-%Mm-%Ss'
			filename = f'{timestart.strftime(filetimeformat)}-{sub[0]}-{str(atword)}-{word}.png'
			extractFrame(wordtimeguessffmpeg, 'images/' + filename)
			wordmeaning = None
			try:
				print(f'defining {word}')
				if os.environ['definewith'] == 'chindict':
					wordmeaning = chindict._lookup_word(word).meaning
					print(f'word success: {word}')
				elif os.environ['definewith'] == 'ai':
					with open('promptdefine.txt', 'r') as promptFile:
						messages = [
							openaireq.constructMessage('system', promptFile.read()),
							openaireq.constructMessage('user', word)
						]
						resp = openaireq.doRequest(messages)
						print(f'got definition: {resp}')
						wordmeaning = resp.split(';')
			except Exception as e: #chindict.errors.NotFound.WordNotFoundException ?
				print(e)
				print(f'word failed: {word}')
				failedwords.append(word)
				continue
			csvline = f"{csvProcessText(word)}|{csvProcessText(pinyin.get(word))}|{csvProcessText('; '.join(wordmeaning))}|{csvProcessText(sub[2])}||<img src=\"{csvProcessText(filename)}\">|{csvProcessText(wordtimeguesspriolevel)}"
			with open('words.csv', 'a', encoding="UTF-8") as csvfile:
				csvfile.write(csvline + '\n')
			donewords.append(word)
		print(f'finished line with {len(donewords)} done words, {len(alrknownwords)} known words, {len(failedwords)} failed words, and {len(alrdonewords)} already done words,')

with open('loglast.txt', 'w', encoding="UTF-8") as logfile:
	logfile.write('FAILED ({}): {}\nADDED ({}): {}'.format(
	len(failedwords), "\n".join(failedwords),
	len(donewords), "\n".join(donewords)
))
