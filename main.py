import os
import subprocess
import jieba
from datetime import datetime
import re
import pinyin
from chin_dict.chindict import ChinDict

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
		'-vf', f"subtitles='{os.environ['subs_path']}':force_style='FontSize=40,FontName=\"Noto Sans SC\"',scale=768:432",
		'-frames:v', '1',
		'-qscale:v', '0',
		filename,
		'-y',
		'-copyts',
	]

	subprocess.call(' '.join(command), stdout=subprocess.DEVNULL)

def csvProcessField(text):
	return text.replace('|', '/')

ignoreknownwords = True

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

with open(os.environ['subs_path'], mode='r', encoding='UTF-8') as subs:
	subsall = subs.read()
	subs = list(chunk(subsall.split('\n'), 4))
	for atsub, sub in enumerate(subs[:-1]):
		print(sub)
		timesplit = sub[1].split(' --> ')
		readtimeformat = '%H:%M:%S,%f'
		timestart = datetime.strptime(timesplit[0], readtimeformat)
		timeend = datetime.strptime(timesplit[1], readtimeformat)
		timediff = timeend - timestart
		print(timediff)
		words = filterNonChinese(list(jieba.cut(sub[2])))
		print(words)
		for atword, word in enumerate(words):
			if word in knownwords and ignoreknownwords:
				continue
			if word in donewords or word in failedwords:
				continue
			ffmpegtimeformat = '%H:%M:%S.%f'
			wordtimeguess = datetime.strftime(timestart + ((atword + 1) / (len(words) + 1)) * timediff, ffmpegtimeformat)
			print(wordtimeguess)
			filetimeformat = '%Hh-%Mm-%Ss'
			filename = f'{timestart.strftime(filetimeformat)}-{sub[0]}-{str(atword)}-{word}.png'
			extractFrame(wordtimeguess, 'images/' + filename)
			wordmeaning = None
			try:
				wordmeaning = chindict._lookup_word(word).meaning
			except: #chindict.errors.NotFound.WordNotFoundException ?
				failedwords.append(word)
				continue
			csvline = f'{csvProcessField(word)}|{csvProcessField(pinyin.get(word))}|{csvProcessField('; '.join(wordmeaning))}|{csvProcessField(sub[2])}||<img src="{filename}">'
			with open('words.csv', 'a', encoding="UTF-8") as csvfile:
				csvfile.write(csvline + '\n')
			donewords.append(word)
			print(f'done {len(donewords)} words')

with open('loglast.txt', 'w', encoding="UTF-8") as logfile:
	logfile.write(f'FAILED ({len(failedwords)}): {"\n".join(failedwords)}\nADDED ({len(donewords)}): {"\n".join(donewords)}')
