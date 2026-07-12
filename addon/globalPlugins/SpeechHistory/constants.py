import config
import os

CONFIG_SECTION = 'speechHistory'
DEFAULT_LOG_FILE_PATH = os.path.join(config.getInstalledUserConfigPath(), "SpeechHistory.log")

DEFAULT_HISTORY_ENTRIES = 500
MIN_HISTORY_ENTRIES = 1
MAX_HISTORY_ENTRIES = 10000000

POST_COPY_NOTHING = 'nothing'
POST_COPY_BEEP = 'beep'
POST_COPY_SPEAK = 'speak'
POST_COPY_BOTH = 'speakAndBeep'
DEFAULT_POST_COPY_ACTION = POST_COPY_BEEP

DEFAULT_BEEP_FREQUENCY = 1500 # Hz
MIN_BEEP_FREQUENCY = 1 # Hz
MAX_BEEP_FREQUENCY = 20000 # Hz

DEFAULT_BEEP_DURATION = 120 # ms
MIN_BEEP_DURATION = 1 # ms
MAX_BEEP_DURATION = 500 # ms

MAX_SPELL_LENGTH = 50

HTML_CONTAINER_START = '<ul style="list-style: none">'
HTML_CONTAINER_END = '</ul>'
HTML_ITEM_START = '<li>'
HTML_ITEM_END = '</li>'

confspec = {
	'maxHistoryLength': f'integer(default={DEFAULT_HISTORY_ENTRIES}, min={MIN_HISTORY_ENTRIES}, max={MAX_HISTORY_ENTRIES})',
	'postCopyAction': f'string(default={DEFAULT_POST_COPY_ACTION})',
	'beepFrequency': f'integer(default={DEFAULT_BEEP_FREQUENCY}, min={MIN_BEEP_FREQUENCY}, max={MAX_BEEP_FREQUENCY})',
	'beepDuration': f'integer(default={DEFAULT_BEEP_DURATION}, min={MIN_BEEP_DURATION}, max={MAX_BEEP_DURATION})',
	'trimWhitespaceFromStart': 'boolean(default=false)',
	'trimWhitespaceFromEnd': 'boolean(default=false)',
	'beep_when_start_or_stop_record': 'boolean(default=True)',
	'write_nvda_speech_output_log_file': 'boolean(default=False)',
	'nvda_speech_output_log_file': f'string(default={DEFAULT_LOG_FILE_PATH})',
	'add_current_time_to_nvda_speech_output_log_file': 'boolean(default=False)'
}

COMMAND_LAYER_GESTURES = {
	"kb:enter": "copyLast",
	"kb:downArrow": "nextString",
	"kb:upArrow": "prevString",
	"kb:home": "lastString",
	"kb:end": "beginningString",
	"kb:h": "showHistory",
	"kb:shift+h": "copyAllHistory",
	"kb:control+h": "clearHistory",
	"kb:alt+h": "copyMostRecentSpeech",
	"kb:r": "startRecording",
	"kb:s": "stopRecording",
	"kb:p": "pauseRecording",
	"kb:x": "repeatMostRecentSpeech",
	"kb:/": "speechHistoryCommandLayerHelp",
}
